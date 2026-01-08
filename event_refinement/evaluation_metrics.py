# event_refinement/evaluation_metrics.py

from typing import List, Dict
import numpy as np
from sklearn import metrics
from collections import Counter

def calculate_partition_metrics(ground_truth_labels: List[int], predicted_sessions: List[List[int]], num_logs: int) -> Dict:
 """
 Calculate事件划分任务Evaluate指标.

 Args:
 ground_truth_labels (List[int]): Length为NList,表示每条LogTrue实事件ID.
 predicted_sessions (List[List[int]]): Predict事件划分,Each子List包含一事件LogIndex.
 num_logs (int): LogTotalNumber.

 Returns:
 Dict: 包含各种Evaluate指标Dictionary.
 """
 if not ground_truth_labels:
 return {"error": "Ground truth labels are missing."}

 # 将 predicted_sessions Convert为与 ground_truth_labels 格式相同Predict标签List
 pred_labels = np.zeros(num_logs, dtype=int)
 for session_id, session_indices in enumerate(predicted_sessions):
 for log_idx in session_indices:
 if log_idx < num_logs:
 pred_labels[log_idx] = session_id

 # 确保两标签ListLength一致
 if len(ground_truth_labels) != len(pred_labels):
 raise ValueError(f"Mismatch in label lengths: ground_truth={len(ground_truth_labels)}, predicted={len(pred_labels)}")

 # Calculate指标
 ari = metrics.adjusted_rand_score(ground_truth_labels, pred_labels)
 nmi = metrics.normalized_mutual_info_score(ground_truth_labels, pred_labels)
 homogeneity = metrics.homogeneity_score(ground_truth_labels, pred_labels)
 completeness = metrics.completeness_score(ground_truth_labels, pred_labels)
 v_measure = metrics.v_measure_score(ground_truth_labels, pred_labels)
 
 # Calculate事件Count
 num_predicted_events = len(set(pred_labels))
 num_true_events = len(set(ground_truth_labels))

 return {
 "Adjusted Rand Index (ARI)": ari,
 "Normalized Mutual Info (NMI)": nmi,
 "Homogeneity": homogeneity,
 "Completeness": completeness,
 "V-Measure": v_measure,
 "Predicted Event Count": num_predicted_events,
 "True Event Count": num_true_events,
 }

def pretty_print_comparison(baseline_metrics: Dict, refined_metrics: Dict):
 """美观地打印基线SumOptimize后指标对比."""
 print("\n" + "="*80)
 print(f"{'Metric':<35} | {'Baseline (Phase 1)':<20} | {'Refined (Phase 2)':<20}")
 print("-"*80)
 
 all_keys = sorted(list(set(baseline_metrics.keys()) | set(refined_metrics.keys())))
 
 for key in all_keys:
 baseline_val = baseline_metrics.get(key)
 refined_val = refined_metrics.get(key)
 
 baseline_str = f"{baseline_val:.4f}" if isinstance(baseline_val, float) else str(baseline_val)
 refined_str = f"{refined_val:.4f}" if isinstance(refined_val, float) else str(refined_val)
 
 print(f"{key:<35} | {baseline_str:<20} | {refined_str:<20}")
 
 print("="*80 + "\n")