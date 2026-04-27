# ablation_experiments/run_ablation.py

import os
import sys
import logging
import json
import torch
import random
import pandas as pd
import time
from typing import List, Dict, Any

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from utils.llm_utils import initialize_llm_client, call_llm_api
from utils.log_helper import logger_init
from data_preprocessing.unified_encoder import UnifiedLogEncoder
from data_preprocessing.dataset import BaseDataset
from event_detector.event_detector import MetaProgrammedDetector
from event_detector import code_generator
from event_refinement.event_refiner import EventRefiner
from event_refinement.model.bi_directional_log_mamba import BiDirectionalLogMamba
from event_refinement.evaluation_metrics import calculate_partition_metrics

# Import Ablation Components
from ablation_models import UniDirectionalLogMamba, LogTransformer
from ablation_prompting import PROMPT_ONE_STAGE_CODE_GEN
from ablation_trainer import train_ablation_model, evaluate_existing_model


class AblationConfig(Config):
    """Extended config for ablation paths."""
    def __init__(self):
        super().__init__()
        self.ablation_artifacts_dir = os.path.join(self.artifacts_dir, "ablation_results")
        os.makedirs(self.ablation_artifacts_dir, exist_ok=True)

        # Define paths for ablation models
        self.uni_mamba_path = os.path.join(self.model_save_dir, f"uni_mamba_{self.dataset}.pth")
        self.transformer_path = os.path.join(self.model_save_dir, f"transformer_{self.dataset}.pth")

        self.MODEL_TYPE = "mamba" 
        self.MAX_SEQ_LEN = 5000 


# ==========================================
# 1. Modified Detector for Ablation
# ==========================================
class AblationDetector(MetaProgrammedDetector):
    def __init__(self, config: AblationConfig, client, mode: str, train_logs: List[Dict]):
        super().__init__(config, client)
        self.mode = mode
        self.train_logs = train_logs 
        self.config = config

    def _generate_and_save_sample(self, logs_ignored: List[Dict]) -> str:
        target_size = self.config.detector_sample_size
        if self.mode == "random_sampling":
            logging.info("[Ablation] Using RANDOM sampling from Train Set.")
            if not self.train_logs: return ""
            selected = random.sample(self.train_logs, min(len(self.train_logs), target_size))
            return "\n".join([self._format_log_for_llm(log) for log in selected])
        else:
            logging.info("[Ablation] Using NOVELTY-AWARE sampling from Train Set.")
            return super()._generate_and_save_sample(self.train_logs)

    def run(self, test_logs: List[Dict], force_regenerate: bool = False):
        if self.mode == "no_multistage":
            logging.info("[Ablation] Running w/o Multi-stage Prompt (One-Shot Code Gen).")
            processor_path = os.path.join(self.config.ablation_artifacts_dir, "processor_onestage.py")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logging.info(f"[OneStage] Attempt {attempt + 1}/{max_retries}...")
                    should_generate = force_regenerate or (attempt > 0) or not os.path.exists(processor_path)
                    if should_generate:
                        samples_str = self._generate_and_save_sample([]) 
                        from event_detector.event_detector import DATASET_GUIDANCE
                        from event_detector.code_generator import load_log_structures 
                        guidance = DATASET_GUIDANCE.get(self.config.dataset, {}).get("context", "")
                        log_structures = load_log_structures(self.config.log_structures_path)
                        dataset_name = getattr(self.config, 'dataset', 'Default')
                        structure_str = log_structures.get(dataset_name, log_structures['Default'])
                        prompt = PROMPT_ONE_STAGE_CODE_GEN.format(
                            dataset_context=guidance, log_samples=samples_str, log_structure=structure_str
                        )
                        code_response = call_llm_api(self.client, prompt, self.config.llm_model_name, self.config)
                        code_clean = code_response.replace("```python", "").replace("```", "").strip()
                        with open(processor_path, "w") as f:
                            f.write(code_clean)
                    return code_generator.apply_and_cluster_events(test_logs, processor_path)
                except Exception as e:
                    logging.error(f"[OneStage] Attempt {attempt + 1} failed with error: {e}")
                    if attempt == max_retries - 1: return [], []
                    else: time.sleep(1)
        elif self.mode == "random_sampling":
            original_path = self.config.event_processor_path
            random_path = os.path.join(self.config.ablation_artifacts_dir, "processor_random.py")
            self.config.event_processor_path = random_path
            original_rule_functions_dir = self.config.rule_functions_dir
            self.config.rule_functions_dir = os.path.join(self.config.ablation_artifacts_dir, "rule_functions")
            os.makedirs(self.config.rule_functions_dir, exist_ok=True)
            original_nl_rules_path = self.config.nl_rules_path
            self.config.nl_rules_path = os.path.join(self.config.ablation_artifacts_dir, "natural_language_rules.json")
            try:
                result = super().run(test_logs, force_regenerate=force_regenerate)
                return result
            finally:
                self.config.event_processor_path = original_path
                self.config.rule_functions_dir = original_rule_functions_dir
                self.config.nl_rules_path = original_nl_rules_path
        else:
            return super().run(test_logs, force_regenerate=force_regenerate)


# ==========================================
# 2. Model Loader & Trainer Handler
# ==========================================
def get_refinement_model(config: AblationConfig, mode: str):
    """
    Factory to load OR TRAIN the correct model for Stage 2.
    Returns: (model, metrics_dict)
    """
    model = None
    weights_path = ""
    model_class = None
    model_name = ""
    metrics = {}

    # 1. Determine Model Class and Path
    if mode == "transformer":
        model_class = LogTransformer
        weights_path = config.transformer_path
        model_name = "Transformer"
    elif mode == "uni_mamba":
        model_class = UniDirectionalLogMamba
        weights_path = config.uni_mamba_path
        model_name = "Uni-Mamba"
    else:
        # Standard Bi-Mamba
        model_class = BiDirectionalLogMamba
        weights_path = config.mamba_model_save_path
        model_name = "Bi-Mamba (Standard)"

    # 2. Check if weights exist, if not -> TRAIN
    if not os.path.exists(weights_path):
        logging.warning(f"Weights for {model_name} not found at {weights_path}.")
        logging.info(f"Initiating training for {model_name}...")
        
        # Call the training function, which now returns (model, metrics)
        model, metrics = train_ablation_model(config, model_class, model_name, weights_path)
    
    else:
        # 3. Load Weights
        logging.info(f"Loading {model_name} from {weights_path}...")
        model = model_class(config)
        state_dict = torch.load(weights_path, map_location=config.device)
        model.load_state_dict(state_dict)
        model.to(config.device)
        model.eval()
        
        # Calculate metrics for the loaded model
        metrics = evaluate_existing_model(config, model, model_name)
    
    return model, metrics


# ==========================================
# 3. Main Experiment Runner
# ==========================================
def run_experiment(mode: str, config: AblationConfig, client, encoder, train_dataset: BaseDataset, test_dataset: BaseDataset):
    logging.info(f"\n{'='*60}\nRUNNING ABLATION: {mode}\n{'='*60}")
    
    # Initialize results container
    results = {
        "mode": mode, 
        "metrics": {}, 
        "inference_time_ms": 0.0,  # Changed to ms for better readability on fast models
        "pretrain_acc": {}         # Store MLM/RPD/ECO acc
    }
    
    # --- Phase I: Agent-Driven Logic Synthesis + Coarse Candidate Partitioning ---
    detector = AblationDetector(config, client, mode, train_dataset.raw_logs)
    
    logging.info(">>> Phase I: Agent-Driven Logic Synthesis")
    # Phase I time is NOT included in the final comparison time
    candidate_partitions, _ = detector.run(test_dataset.raw_logs, force_regenerate=False)
    
    if not candidate_partitions:
        logging.error(f"!!! Phase I failed for mode: {mode}. Returning -1 metrics.")
        results["metrics"] = {"Adjusted Rand Index (ARI)": -1}
        return results

    logging.info(f"Phase I finished. Found {len(candidate_partitions)} coarse candidate partitions.")

    # --- Phase II: Log Representation Learning & Refinement ---
    refined_events = candidate_partitions
    inference_time = 0.0
    
    if mode == "no_refinement":
        logging.info(">>> Phase II: Skipped (Ablation)")
        # No model involved, metrics are N/A
        results["pretrain_acc"] = {"MLM": "N/A", "RPD": "N/A", "ECO": "N/A"}
        
    else:
        logging.info(f">>> Phase II: Refinement ({mode})")

        config.MODEL_TYPE = "mamba"
        
        # Determine model type based on mode
        model_mode = "bi_mamba"
        if mode == "uni_mamba": 
            model_mode = "uni_mamba"
        elif mode == "transformer": 
            model_mode = "transformer"
            config.MODEL_TYPE = "transformer"
            config.MAX_SEQ_LEN = 5000
            logging.info(f"[Ablation] Config updated: MODEL_TYPE='transformer', MAX_SEQ_LEN={config.MAX_SEQ_LEN}")
        
        # Get trained model AND pre-training metrics
        model, pretrain_metrics = get_refinement_model(config, model_mode)
        
        # Store pre-training metrics
        results["pretrain_acc"] = {
            "MLM": pretrain_metrics.get("mlm_acc", 0.0),
            "RPD": pretrain_metrics.get("rpd_acc", 0.0),
            "ECO": pretrain_metrics.get("eco_acc", 0.0)
        }
        
        refiner = EventRefiner(config, model, encoder, test_dataset.raw_logs)
        
        # === CRITICAL: Measure ONLY Inference Time ===
        # We want to measure how long the model takes to refine the sessions
        # Exclude initialization overhead if possible, focus on the .refine() call
        
        # Warmup (optional, but good for CUDA timing) if using GPU
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            
        t0 = time.time()
        refined_events = refiner.refine(candidate_partitions)
        
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        t1 = time.time()
        
        inference_time = t1 - t0
        logging.info(f"Refinement Inference Time: {inference_time:.4f}s")
        # =============================================

    results["inference_time_ms"] = inference_time * 1000.0 # Convert to ms
    
    # --- Evaluation ---
    if test_dataset.manual_labels:
        metrics = calculate_partition_metrics(test_dataset.manual_labels, refined_events, len(test_dataset.raw_logs))
        results["metrics"] = metrics
        logging.info(f"Results for {mode}: ARI={metrics.get('Adjusted Rand Index (ARI)', 0):.4f}")
    else:
        logging.warning("No ground truth labels found for test set.")

    return results

def main():
    config = AblationConfig()
    logger_init(log_file_name=f'{config.dataset}.log', log_level=logging.DEBUG, log_dir=config.logs_save_dir)
    logging.info("Config loaded successfully.")

    client = initialize_llm_client(config)
    
    # 1. Load Data & Encoder
    if not os.path.exists(config.encoder_save_path):
        logging.error("Encoder not found. Please run pretraining first.")
        return

    encoder: UnifiedLogEncoder = UnifiedLogEncoder.load(config.encoder_save_path)

    # Update config vocab sizes
    config.template_vocab_size = encoder.template_vocab_size
    config.param_vocab_size = encoder.param_vocab_size

    train_dataset = BaseDataset(config, mode='train', data_source=config.data_source_train)
    test_dataset = BaseDataset(config, mode='eval', data_source=config.data_source_eval)

    # 2. Define Ablation Modes
    modes = [
        "full_model",        # lognexus (BiMamba)
        # "no_multistage",     # w/o Multi-stage Prompt
        # "random_sampling",   # w/o Exemplar Sampling
        # "no_refinement",     # w/o Mamba Refinement
        # "uni_mamba",         # w/ Bi-Mamba -> Uni-Mamba
        # "transformer"        # w/ Mamba -> Transformer
    ]

    all_results = []

    # 3. Run Loop
    for mode in modes:
        try:
            res = run_experiment(mode, config, client, encoder, train_dataset, test_dataset)
            all_results.append(res)
        except Exception as e:
            logging.error(f"Failed ablation {mode}: {e}", exc_info=True)

    # 4. Save & Print Summary
    summary_path = os.path.join(config.ablation_artifacts_dir, "final_summary.csv")
    
    # Flatten for CSV
    csv_data = []
    for r in all_results:
        row = {
            "Mode": r["mode"], 
            "Inference Time (ms)": f"{r['inference_time_ms']:.2f}",
            "MLM Acc": r["pretrain_acc"].get("MLM", "N/A"),
            "RPD Acc": r["pretrain_acc"].get("RPD", "N/A"),
            "ECO Acc": r["pretrain_acc"].get("ECO", "N/A"),
        }
        # Format metrics nicely
        for k, v in r["metrics"].items():
            if isinstance(v, float):
                row[k] = f"{v:.4f}"
            else:
                row[k] = v
        csv_data.append(row)
    
    df = pd.DataFrame(csv_data)
    df.to_csv(summary_path, index=False)
    
    print("\n" + "="*80)
    print("FINAL ABLATION RESULTS")
    print("="*80)
    # Use to_markdown if available, else simple print
    try:
        print(df.to_markdown(index=False))
    except ImportError:
        print(df.to_string(index=False))

if __name__ == "__main__":
    main()
