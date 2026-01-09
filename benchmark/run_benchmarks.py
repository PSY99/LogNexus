# benchmark/run_benchmarks.py

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from utils.llm_utils import initialize_llm_client
from data_preprocessing.unified_encoder import UnifiedLogEncoder
from data_preprocessing.dataset import BaseDataset
from event_refinement.evaluation_metrics import calculate_partition_metrics

from benchmark.traditional import TraditionalBaseline
from benchmark.deepcase_adapter import DeepCaseAdapter
from benchmark.llm_zeroshot import LLMBaseline
from benchmark.pretrained import PretrainedBaseline

def main():
    parser = argparse.ArgumentParser(description="Run Benchmarks with Train/Test Split")
    parser.add_argument('--methods', nargs='+', 
                        default=['llm_knowledge'],
                        help='List of methods: traditional, deepcase, pretrained, llm_naive, llm_knowledge, llm_cot')
    args = parser.parse_args()

    # 1. Setup & Config
    config: Config = Config()
    
    # Encoder loading logic...
    if not os.path.exists(config.encoder_save_path) and 'traditional' in args.methods:
        logging.error("Encoder not found. Please run training/preprocessing first.")
        return
    
    try:
        encoder = UnifiedLogEncoder.load(config.encoder_save_path)
    except:
        encoder = None
        logging.warning("UnifiedLogEncoder could not be loaded. Methods relying on it may fail.")

    # 2. Load Data
    logging.info("Loading Training Data...")
    train_dataset = BaseDataset(config, mode='train', data_source=config.data_source_train)
    train_logs = train_dataset.raw_logs
    
    logging.info("Loading Evaluation (Test) Data...")
    test_dataset = BaseDataset(config, mode='eval', data_source=config.data_source_eval)
    test_logs = test_dataset.raw_logs
    ground_truth = test_dataset.manual_labels 

    if not ground_truth:
        logging.warning("No ground truth labels found. Metrics will be empty.")

    cluster_num = len(set(ground_truth)) if ground_truth else 10
    results = {}
    save_dir = Path(config.result_dir) / "benchmark_results"
    save_dir.mkdir(parents=True, exist_ok=True)

    # 3. Run Methods

    # --- Method A: Traditional ---
    if 'traditional' in args.methods and encoder:
        try:
            logging.info(">>> Running Traditional Baseline...")
            baseline = TraditionalBaseline(n_clusters=cluster_num)
            baseline.fit(train_logs)
            predicted_sessions = baseline.predict(test_logs)
            if ground_truth:
                metrics = calculate_partition_metrics(ground_truth, predicted_sessions, len(test_logs))
                results['Traditional'] = metrics
                logging.info(f"Traditional Metrics: {metrics}")
        except Exception as e:
            logging.error(f"Traditional Baseline Failed: {e}", exc_info=True)

    # --- Method B: DeepCASE ---
    if 'deepcase' in args.methods and encoder:
        try:
            logging.info(">>> Running DeepCASE Baseline...")
            timeout = getattr(config, 'detector_session_gap_seconds', 300) 
            adapter = DeepCaseAdapter(
                template_map=encoder.template_to_id,
                timeout=timeout,
                device=config.device
            )
            adapter.fit(train_logs)
            predicted_sessions, _ = adapter.predict(test_logs)
            if ground_truth:
                metrics = calculate_partition_metrics(ground_truth, predicted_sessions, len(test_logs))
                results['DeepCASE'] = metrics
                logging.info(f"DeepCASE Metrics: {metrics}")
        except Exception as e:
            logging.error(f"DeepCASE Baseline Failed: {e}", exc_info=True)

    # --- Method C: LLM Baselines (Naive, Few-shot, CoT) ---
    llm_methods = [m for m in args.methods if m.startswith('llm_')]
    
    if llm_methods:
        logging.info(f">>> Running LLM Baselines: {llm_methods}")
        client = initialize_llm_client(config)
        
        if not client:
            logging.error("LLM Client initialization failed.")
        else:
            for method_name in llm_methods:
                try:
                    strategy = method_name.split('_')[1]
                    logging.info(f"Running LLM Strategy: {strategy.upper()}")
                    
                    chunk_size = 800
                    overlap = 100
                    
                    baseline = LLMBaseline(
                        client, 
                        config, 
                        strategy=strategy, 
                        chunk_size=chunk_size, 
                        overlap=overlap
                    )
                    
                    predicted_sessions = baseline.predict(test_logs)
                    
                    if ground_truth:
                        metrics = calculate_partition_metrics(ground_truth, predicted_sessions, len(test_logs))
                        key_name = f"LLM_{strategy.capitalize()}"
                        results[key_name] = metrics
                        logging.info(f"{key_name} Metrics: {metrics}")
                        
                except Exception as e:
                    logging.error(f"LLM Method {method_name} Failed: {e}", exc_info=True)

    # --- Method D: Pre-trained ---
    if 'pretrained' in args.methods:
        try:
            logging.info(">>> Running Pre-trained Baseline...")
            baseline = PretrainedBaseline(
                base_model_path='./bert-base-uncased/', 
                model_save_dir=config.model_save_dir, 
                n_clusters=cluster_num,
                device=config.device
            )
            baseline.fit(train_logs)
            predicted_sessions = baseline.predict(test_logs)
            if ground_truth:
                metrics = calculate_partition_metrics(ground_truth, predicted_sessions, len(test_logs))
                results['Pretrained'] = metrics
                logging.info(f"Pretrained Metrics: {metrics}")
        except Exception as e:
            logging.error(f"Pretrained Baseline Failed: {e}", exc_info=True)

    # 4. Save Results
    output_file = save_dir / "benchmark_metrics.json"
    if output_file.exists():
        with open(output_file, 'r') as f:
            existing_results = json.load(f)
        existing_results.update(results)
        results = existing_results

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)
    
    logging.info("Benchmark finished. Results saved.")

if __name__ == "__main__":
    main()