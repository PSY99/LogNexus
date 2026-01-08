# ./event_refinement/event_refiner.py

import os
import json
import logging
import copy
from typing import List, Dict, DefaultDict, Optional, Tuple, Any
from datetime import datetime, timedelta, date
from collections import defaultdict
from itertools import groupby

import torch
from tqdm import tqdm

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from data_preprocessing.unified_encoder import UnifiedLogEncoder
from event_refinement.model.bi_directional_log_mamba import BiDirectionalLogMamba


class EventRefiner:
 def __init__(self, config: "Config", model: "BiDirectionalLogMamba", encoder: "UnifiedLogEncoder", raw_logs: List[Dict]):
 self.config = config
 self.model = model
 self.encoder = encoder
 self.raw_logs = copy.deepcopy(raw_logs)
 
 self.model.eval()
 self.model.to(self.config.device)

 self.is_transformer = False
 if hasattr(self.config, 'MODEL_TYPE') and self.config.MODEL_TYPE.lower() == 'transformer':
 self.is_transformer = True
 self.max_seq_len = getattr(self.config, 'MAX_SEQ_LEN', 512)
 logging.info(f"EventRefiner detected Transformer model. Using sliding window size: {self.max_seq_len}")
 else:
 logging.info("EventRefiner using Full-Context model (e.g., Mamba).")
 
 self.mask_template_id = self.encoder.template_to_id.get(self.config.MASK_TOKEN)
 if self.mask_template_id is None:
 raise Valueerror(f"'{self.config.MASK_TOKEN}' not found in encoder's template vocabulary!")

 self.param_rules: Optional[Dict[str, List[str]]] = None
 rules_path = os.path.join(os.path.dirname(__file__), 'parameter_rules.json')
 try:
 with open(rules_path, 'r') as f:
 all_rules = json.load(f)
 if self.config.dataset in all_rules:
 self.param_rules = all_rules[self.config.dataset]
 logging.info(f"Successfully loaded parameter rules for dataset '{self.config.dataset}'.")
 logging.info(f"Primary Attributes: {self.param_rules.get('PrimaryAttributes', [])}")
 logging.info(f"Secondary Attributes: {self.param_rules.get('SecondaryAttributes', [])}")
 else:
 logging.warning(f"No parameter rules found for dataset '{self.config.dataset}' in {rules_path}.")
 except FileNotFounderror:
 logging.warning(f"Parameter rules file not found at {rules_path}. Skipping parameter-based refinement.")
 except Exception as e:
 logging.error(f"error loading parameter rules: {e}")

 logging.info("Preprocessing and globally sorting logs for internal use...")
 for i, log in enumerate(self.raw_logs):
 log['_original_index'] = i
 if isinstance(log['Timestamp'], str):
 log['_datetime'] = datetime.strptime(log['Timestamp'], '%Y-%m-%d %H:%M:%S')
 else:
 log['_datetime'] = log['Timestamp']
 
 self.raw_logs.sort(key=lambda log: log['_datetime'])
 
 self.original_to_new_index_map: Dict[int, int] = {log['_original_index']: i for i, log in enumerate(self.raw_logs)}
 self.new_to_original_index_map: Dict[int, int] = {i: log['_original_index'] for i, log in enumerate(self.raw_logs)}
 
 logging.info("EventRefiner initialized.")

 def _translate_and_sort_sessions(self, initial_sessions: List[List[int]]) -> List[List[int]]:
 translated_sessions = []
 for session in initial_sessions:
 if not session: continue
 new_session = [self.original_to_new_index_map.get(old_idx) for old_idx in session]
 if any(idx is None for idx in new_session): continue
 translated_sessions.append(sorted(new_session))
 translated_sessions.sort(key=lambda s: self.raw_logs[s[0]]['_datetime'] if s else datetime.max)
 return translated_sessions

 def _translate_back_to_original_indices(self, refined_sessions: List[List[int]]) -> List[List[int]]:
 return [[self.new_to_original_index_map[new_idx] for new_idx in session] for session in refined_sessions if session]

 def _group_sessions_by_day(self, sessions: List[List[int]]) -> Dict[date, List[List[int]]]:
 sessions_by_day: DefaultDict[date, List[List[int]]] = defaultdict(list)
 for session in sessions:
 if not session: continue
 sessions_by_day[self.raw_logs[session[0]]['_datetime'].date()].append(session)
 return {day: sessions_by_day[day] for day in sorted(sessions_by_day.keys())}
 
 def _get_param_values(self, log_idx: int, keys: List[str]) -> Tuple[Any, ...]:
 log = self.raw_logs[log_idx]
 return tuple(log.get(key) for key in keys)

 def _split_based_on_parameter_rules(self, sessions: List[List[int]]) -> List[List[int]]:
 """
 According toParameterRulesplitevent,samewhen保证when序性并合理processNoneLog.
 """
 if not self.param_rules:
 return sessions

 primary_keys = self.param_rules.get("PrimaryAttributes", [])
 secondary_keys = self.param_rules.get("SecondaryAttributes", [])
 if not primary_keys:
 return sessions

 logging.debug("Applying parameter-based splitting rules...")
 final_sessions = []
 num_sessions_before = len(sessions)
 
 for session in sessions:
 # session 已经is按when间Sort
 if len(session) <= 1:
 if session: final_sessions.append(session)
 continue

 # 1. According to主属性Value对Log进lineGroup
 groups: Dict[Optional[Tuple], List[int]] = defaultdict(list)
 for log_idx in session:
 primary_values = self._get_param_values(log_idx, primary_keys)
 key = primary_values if not all(v is None for v in primary_values) else None
 groups[key].append(log_idx)

 if len(groups) <= 1 or (None in groups.keys() and len(groups) == 2):
 final_sessions.append(session)
 continue

 # 2. splitevent,并分离出主属性asNoneLog
 base_sessions = [grp for key, grp in groups.items() if key is not None]
 logs_to_redistribute = groups.get(None, [])

 # 3. times属性归并：尝试willNoneLogAccording totimes要属性归并to已split子eventin
 if logs_to_redistribute and secondary_keys and base_sessions:
 secondary_value_map: Dict[Tuple, int] = {}
 for i, sub_session in enumerate(base_sessions):
 for log_idx in sub_session:
 sec_values = self._get_param_values(log_idx, secondary_keys)
 if not all(v is None for v in sec_values):
 secondary_value_map[sec_values] = i
 
 unassigned_logs = []
 for log_idx in logs_to_redistribute:
 sec_values = self._get_param_values(log_idx, secondary_keys)
 target_session_idx = secondary_value_map.get(sec_values)
 if target_session_idx is not None:
 base_sessions[target_session_idx].append(log_idx)
 else:
 unassigned_logs.append(log_idx)
 logs_to_redistribute = unassigned_logs

 # 4. 【NewLogic】process剩余No法归并NoneLog：will它们MergetoMax子eventin
 if logs_to_redistribute and base_sessions:
 # 找toMax子event作as“主event”
 largest_session_idx = max(range(len(base_sessions)), key=lambda i: len(base_sessions[i]))
 # willNo法归并Log全部并入主event
 base_sessions[largest_session_idx].extend(logs_to_redistribute)
 # 【关键】Merge后必须重NewSort以维持when序性
 base_sessions[largest_session_idx].sort()
 elif logs_to_redistribute:
 # Ifsplit后没hasbase_sessions（allLog主属性都asNone）,then它们本身就isoneevent
 final_sessions.append(logs_to_redistribute)

 final_sessions.extend(base_sessions)

 # 5. 【关键】对all最终GenerateeventList按Startwhen间进lineSort,Ensure后续Stepinputiswhen序positive确
 final_sessions.sort(key=lambda s: s[0] if s else float('inf'))
 
 num_sessions_after = len(final_sessions)
 if num_sessions_before != num_sessions_after:
 logging.debug(f"Parameter-based splitting changed session count from {num_sessions_before} to {num_sessions_after}.")
 
 return final_sessions

 def _check_top_k_belongingness(self, session_indices: List[int]) -> List[bool]:
 session_len = len(session_indices)
 if session_len < 2:
 return [True] * session_len

 # 1. prepare备原始Data Tensor
 original_encoded = [self.encoder.encode(self.raw_logs[i]) for i in session_indices]
 original_template_ids = torch.tensor([enc['template_id'] for enc in original_encoded], dtype=torch.long)
 
 param_ids_list = [torch.tensor(enc['param_ids'], dtype=torch.long) for enc in original_encoded]
 # Pad parameters (sequence level padding is handled below for Transformers)
 padded_params = torch.nn.utils.rnn.pad_sequence(param_ids_list, batch_first=True, padding_value=self.encoder.param_to_id.get(self.config.PAD_TOKEN, 0))

 all_is_in_top_k = []
 batch_size = self.config.refiner_batch_size

 for i in range(0, session_len, batch_size):
 start_idx = i
 end_idx = min(i + batch_size, session_len)
 current_batch_size = end_idx - start_idx
 
 # --- 分support A: Transformer Model (Use滑动Window) ---
 if self.is_transformer:
 # Build batch List,Each元素is截取后Window
 batch_templates_list = []
 batch_params_list = []
 batch_mask_indices = []

 for k in range(current_batch_size):
 target_idx_in_session = start_idx + k
 
 # CalculateWindow范围：以 target asin心
 half_window = self.max_seq_len // 2
 win_start = max(0, target_idx_in_session - half_window)
 win_end = min(session_len, win_start + self.max_seq_len)
 
 # If右边界越界,且左边还hasNull间,往左移动Window以填满 max_seq_len
 if (win_end - win_start) < self.max_seq_len and win_start > 0:
 win_start = max(0, win_end - self.max_seq_len)
 
 # 切片
 template_slice = original_template_ids[win_start:win_end]
 param_slice = padded_params[win_start:win_end]
 
 # Calculate mask in切片in相对position
 relative_mask_idx = target_idx_in_session - win_start
 
 batch_templates_list.append(template_slice)
 batch_params_list.append(param_slice)
 batch_mask_indices.append(relative_mask_idx)

 # Pad batches (因as Session 头尾Window可能不足 max_seq_len)
 batch_template_ids = torch.nn.utils.rnn.pad_sequence(
 batch_templates_list, batch_first=True, padding_value=self.encoder.template_to_id.get(self.config.PAD_TOKEN, 0)
 )
 batch_param_ids = torch.nn.utils.rnn.pad_sequence(
 batch_params_list, batch_first=True, padding_value=self.encoder.param_to_id.get(self.config.PAD_TOKEN, 0)
 )
 
 mask_seq_indices = torch.tensor(batch_mask_indices) # 相对position
 mask_batch_indices = torch.arange(current_batch_size)

 # --- 分support B: Mamba / RNN Model (全量上下文) ---
 else:
 # 保持原hasLogic：directly复制整 Session
 batch_template_ids = original_template_ids.repeat(current_batch_size, 1)
 batch_param_ids = padded_params.unsqueeze(0).repeat(current_batch_size, 1, 1)
 
 mask_batch_indices = torch.arange(current_batch_size)
 mask_seq_indices = torch.arange(start_idx, end_idx) # 绝对position

 # --- 公共推理Logic ---
 # 应用 Mask
 batch_template_ids[mask_batch_indices, mask_seq_indices] = self.mask_template_id
 
 batch_template_ids = batch_template_ids.to(self.config.device)
 batch_param_ids = batch_param_ids.to(self.config.device)

 with torch.no_grad():
 # Model forward
 mlm_logits, _, _ = self.model(batch_template_ids, batch_param_ids)

 # Get Mask positionPredict结果
 target_logits = mlm_logits[mask_batch_indices, mask_seq_indices, :]
 target_template_ids = original_template_ids[start_idx:end_idx].to(self.config.device)
 
 _, top_k_indices = torch.topk(target_logits, k=self.config.refiner_top_k, dim=-1)
 is_in_top_k_batch = (top_k_indices == target_template_ids.unsqueeze(1)).any(dim=1)
 
 all_is_in_top_k.append(is_in_top_k_batch.cpu())

 final_is_in_top_k = torch.cat(all_is_in_top_k)
 
 # process未知模板 (-1)
 final_is_in_top_k[original_template_ids == -1] = True
 
 return final_is_in_top_k.tolist()

 def _calculate_session_coherence(self, session_indices: List[int]) -> float:
 if len(session_indices) <= 1: return 1.0
 is_in_top_k_list = self._check_top_k_belongingness(session_indices)
 return sum(is_in_top_k_list) / len(is_in_top_k_list)
 
 def _split_based_on_belongingness(self, initial_sessions: List[List[int]]) -> List[List[int]]:
 split_sessions = []
 for session_indices in initial_sessions:
 session_indices.sort()
 if len(session_indices) <= 1:
 if session_indices: split_sessions.append(session_indices)
 continue

 if self.config.EXEMPT_IF_PID_CONSISTENT:
 pids = {self.raw_logs[i].get('PID') for i in session_indices}
 if len(pids) == 1 and next(iter(pids)) is not None:
 split_sessions.append(session_indices)
 continue
 
 if self.config.EXEMPT_IF_TIMESPAN_LESS_THAN_S > 0:
 start_time = self.raw_logs[session_indices[0]]['_datetime']
 end_time = self.raw_logs[session_indices[-1]]['_datetime']
 if (end_time - start_time).total_seconds() < self.config.EXEMPT_IF_TIMESPAN_LESS_THAN_S:
 split_sessions.append(session_indices)
 continue

 coherence_score = self._calculate_session_coherence(session_indices)
 if coherence_score >= self.config.COHERENCE_THRESHOLD_TO_SKIP_SPLIT:
 split_sessions.append(session_indices)
 continue

 is_in_top_k_list = self._check_top_k_belongingness(session_indices)
 grouped_by_coherence = groupby(zip(session_indices, is_in_top_k_list), key=lambda x: x[1])

 for is_coherent, group in grouped_by_coherence:
 group_log_indices = [item[0] for item in group]
 if is_coherent:
 if group_log_indices:
 split_sessions.append(group_log_indices)
 else:
 for log_idx in group_log_indices:
 split_sessions.append([log_idx])
 
 return split_sessions

 def _get_log_content_key(self, log_index: int) -> str:
 log_entry = self.raw_logs[log_index]
 template = log_entry.get('EventTemplate', '')
 params = log_entry.get('Parameters', []) 
 return template + str(params)

 def _merge_adjacent_sessions(self, sessions: List[List[int]]) -> List[List[int]]:
 if self.config.MERGE_IDENTICAL_CONTENT_WINDOW_S <= 0 or len(sessions) < 2:
 return sessions

 merged_sessions = [sessions[0]]
 
 for i in range(1, len(sessions)):
 prev_session = merged_sessions[-1]
 current_session = sessions[i]

 prev_session_end_time = self.raw_logs[prev_session[-1]]['_datetime']
 current_session_start_time = self.raw_logs[current_session[0]]['_datetime']
 time_gap = (current_session_start_time - prev_session_end_time).total_seconds()

 if time_gap > self.config.MERGE_IDENTICAL_CONTENT_WINDOW_S:
 merged_sessions.append(current_session)
 continue

 len_prev = len(prev_session)
 len_curr = len(current_session)
 should_merge = False

 if len_prev == 1 and len_curr == 1:
 content_key_prev = self._get_log_content_key(prev_session[0])
 content_key_curr = self._get_log_content_key(current_session[0])
 if content_key_prev == content_key_curr:
 should_merge = True
 
 elif len_prev > 1 and len_curr == 1:
 content_key_curr = self._get_log_content_key(current_session[0])
 prev_content_keys = {self._get_log_content_key(idx) for idx in prev_session}
 if content_key_curr in prev_content_keys:
 should_merge = True

 elif len_prev == 1 and len_curr > 1:
 content_key_prev = self._get_log_content_key(prev_session[0])
 curr_content_keys = {self._get_log_content_key(idx) for idx in current_session}
 if content_key_prev in curr_content_keys:
 should_merge = True
 
 if should_merge:
 merged_sessions[-1].extend(current_session)
 merged_sessions[-1].sort() 
 else:
 merged_sessions.append(current_session)
 
 num_before = len(sessions)
 num_after = len(merged_sessions)
 if num_before > num_after:
 logging.debug(f"Merged {num_before} sessions into {num_after} based on multi-scenario rules.")
 
 return merged_sessions

 def refine(self, initial_sessions: List[List[int]]) -> List[List[int]]:
 """
 【V7.1 最终版Optimize流程】
 ExecuteeventOptimize,包含ParameterRulesplit、语义切分and多场景Merge.
 """
 logging.info(f"Starting refinement for {len(initial_sessions)} initial sessions...")
 
 internal_sessions = self._translate_and_sort_sessions(initial_sessions)
 sessions_grouped_by_day = self._group_sessions_by_day(internal_sessions)
 
 all_refined_sessions_internal = []
 progress_bar = tqdm(sessions_grouped_by_day.items(), desc="Refining Events Day by Day")
 
 for day, daily_sessions in progress_bar:
 progress_bar.set_postfix_str(f"Day {day}, {len(daily_sessions)} sessions")
 
 # Step A: ParameterRulesplit (硬Rule优先,已fixwhen序问题)
 sessions_after_param_split = self._split_based_on_parameter_rules(daily_sessions)
 
 # Step B: 语义切分 (Model软Rule,现ininputiswhen序positive确)
 sessions_after_semantic_split = self._split_based_on_belongingness(sessions_after_param_split)
 
 # Step C: [保障性Sort] 再timesSort,EnsureMergeLogicinput绝对positive确
 sessions_after_semantic_split.sort(key=lambda s: s[0] if s else float('inf'))

 # Step D: 多场景Merge
 sessions_after_merge = self._merge_adjacent_sessions(sessions_after_semantic_split)
 
 all_refined_sessions_internal.extend(sessions_after_merge)

 all_refined_sessions_internal.sort(key=lambda s: s[0] if s else float('inf'))
 final_sessions_original_idx = self._translate_back_to_original_indices(all_refined_sessions_internal)

 logging.info(f"Refinement complete. Final session count: {len(final_sessions_original_idx)}")
 return final_sessions_original_idx
 

