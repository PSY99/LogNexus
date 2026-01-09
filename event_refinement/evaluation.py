# .event_refinement/evaluation.py

import os
import logging 
import json
from pathlib import Path
from typing import List, Dict

import torch
from tqdm import tqdm

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from data_preprocessing.unified_encoder import UnifiedLogEncoder
from data_preprocessing.dataset import BaseDataset
from event_refinement.model.bi_directional_log_mamba import BiDirectionalLogMamba
from event_refinement.evaluation_metrics import calculate_partition_metrics, pretty_print_comparison
from event_refinement.event_refiner import EventRefiner
# from event_refinement.event_refiner_copy import EventRefiner

# =================================================================================
# 新增：辅助函数，用于将事件保存为人类可读的日志文件
# =================================================================================

def _convert_sessions_to_event_dict(sessions: List[List[int]], raw_logs: List[Dict]) -> Dict[int, List[Dict]]:
    """
    将基于索引的 session 列表转换为基于事件ID的字典。
    这是将内部数据结构适配到保存函数所需格式的关键步骤。

    Args:
        sessions (List[List[int]]): 事件划分，每个子列表包含一个事件的日志索引。
        raw_logs (List[Dict]): 包含所有已解析日志字典的完整列表。

    Returns:
        Dict[int, List[Dict]]: 一个字典，键是事件ID（这里用session的索引），值是该事件包含的日志字典列表。
    """
    events_by_id = {}
    for i, session_indices in enumerate(sessions):
        if not session_indices:  # 跳过空事件
            continue
        # 根据索引从 raw_logs 中获取完整的日志字典
        events_by_id[i] = [raw_logs[log_idx] for log_idx in session_indices]
    return events_by_id

def _save_events_to_file(events_by_id: dict, output_filepath: Path):
    """
    将事件字典保存到指定文件，覆盖写入。
    （此函数直接来自您的请求，稍作修改以使用 Path 对象）
    """
    logging.info(f"--- Saving events to file: {output_filepath} ---")
    # 按时间戳对整个事件列表进行排序，确保文件内容有序
    # 过滤掉可能存在的空事件
    events_to_save = sorted([e for e in events_by_id.values() if e], key=lambda e: e[0]['Timestamp'])
    
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            for event_logs in tqdm(events_to_save, desc=f"Saving to {output_filepath.name}"):
                # 确保事件内部的日志也是按时间排序的
                sorted_event_logs = sorted(event_logs, key=lambda log: log['Timestamp'])
                for log_dict in sorted_event_logs:
                    f.write(log_dict['LogContent'].rstrip() + '\n')
                f.write('\n') # 事件之间用空行分隔
        logging.info(f"Successfully saved {len(events_to_save)} events to {output_filepath}")
    except Exception as e:
        logging.error(f"Failed to save events to file {output_filepath}: {e}")

# =================================================================================
# 主评估函数
# =================================================================================

def run_evaluation(config: Config):
    """
    执行完整的事件优化评估流程。
    """
    # --- 1. 加载预训练组件 ---
    logging.info("Step 1: Loading prerequisite components (Encoder and Model)...")
    
    # 加载编码器
    if not os.path.exists(config.encoder_save_path):
        raise FileNotFoundError(f"Encoder not found at '{config.encoder_save_path}'. Please run training first to generate it.")
    encoder: UnifiedLogEncoder = UnifiedLogEncoder.load(config.encoder_save_path)
    config.template_vocab_size = encoder.template_vocab_size
    config.param_vocab_size = encoder.param_vocab_size
    logging.info("UnifiedLogEncoder loaded successfully.")

    # 加载模型
    model: BiDirectionalLogMamba = BiDirectionalLogMamba(config).to(config.device)
    if not os.path.exists(config.mamba_model_save_path):
        raise FileNotFoundError(f"Model weights not found at '{config.mamba_model_save_path}'. Please provide a trained model.")
    model.load_state_dict(torch.load(config.mamba_model_save_path, map_location=config.device))
    logging.info(f"LogMamba model loaded from '{config.mamba_model_save_path}'.")

    # --- 2. 加载数据和阶段一结果 ---
    logging.info("\nStep 2: Loading data and running Phase 1 initial session detection...")
    try:
        evaluation_dataset = BaseDataset(config, mode='eval', data_source=config.data_source_eval)
        raw_logs = evaluation_dataset.raw_logs
        initial_sessions = evaluation_dataset.get_sessions_for_eval()
        ground_truth_labels = evaluation_dataset.manual_labels
        logging.info(f"Data loaded. Found {len(raw_logs)} logs and {len(initial_sessions)} initial baseline sessions.")
    except Exception as e:
        raise RuntimeError(f"Failed to load data and get initial sessions: {e}", exc_info=True)

    # --- 3. 执行阶段二优化 ---
    logging.info("\nStep 3: Initializing EventRefiner and running Phase 2 refinement...")
    refiner = EventRefiner(config, model, encoder, raw_logs)
    refined_sessions = refiner.refine(initial_sessions)
    logging.info(f"Refinement complete. Generated {len(refined_sessions)} refined sessions.")
    
    # --- 4. 评估和对比结果 ---
    logging.info("\nStep 4: Calculating and comparing evaluation metrics...")
    if not ground_truth_labels:
        logging.warning("Cannot perform quantitative evaluation because ground truth labels are missing.")
        metrics_results = {
            "baseline_stats": {"session_count": len(initial_sessions)},
            "refined_stats": {"session_count": len(refined_sessions)},
            "notes": "Quantitative metrics (ARI, NMI, etc.) could not be calculated due to missing ground truth labels."
        }
    else:
        num_logs = len(raw_logs)
        logging.info("Calculating metrics for baseline (Phase 1) sessions...")
        baseline_metrics = calculate_partition_metrics(ground_truth_labels, initial_sessions, num_logs)
        
        logging.info("Calculating metrics for refined (Phase 2) sessions...")
        refined_metrics = calculate_partition_metrics(ground_truth_labels, refined_sessions, num_logs)
        
        # 打印对比表格
        pretty_print_comparison(baseline_metrics, refined_metrics)
        
        metrics_results = {
            "baseline_metrics": baseline_metrics,
            "refined_metrics": refined_metrics
        }

    # --- 5. 保存结果 (已更新) ---
    logging.info("\nStep 5: Saving all results...")
    output_dir = Path(config.artifacts_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 5.1 保存优化后的事件划分 (JSON格式，用于机器处理)
    refined_sessions_path = output_dir / "refined_sessions.json"
    with open(refined_sessions_path, 'w') as f:
        json.dump(refined_sessions, f, indent=2)
    logging.info(f"Refined session indices saved to: {refined_sessions_path}")

    # 5.2 保存评估指标
    metrics_path = output_dir / "evaluation_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics_results, f, indent=4)
    logging.info(f"Evaluation metrics saved to: {metrics_path}")

    # 5.3 【新增】保存基线事件为人类可读的日志文件
    baseline_events_dict = _convert_sessions_to_event_dict(initial_sessions, raw_logs)
    baseline_output_path = output_dir / "baseline_events_readable.log"
    _save_events_to_file(baseline_events_dict, baseline_output_path)

    # 5.4 【新增】保存优化后事件为人类可读的日志文件
    refined_events_dict = _convert_sessions_to_event_dict(refined_sessions, raw_logs)
    refined_output_path = output_dir / "refined_events_readable.log"
    _save_events_to_file(refined_events_dict, refined_output_path)


    logging.info("\nEvaluation script finished successfully.")


if __name__ == "__main__":
    config = Config()
    run_evaluation(config)


    