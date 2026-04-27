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
            raise ValueError(f"'{self.config.MASK_TOKEN}' not found in encoder's template vocabulary!")

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
        except FileNotFoundError:
            logging.warning(f"Parameter rules file not found at {rules_path}. Skipping parameter-based refinement.")
        except Exception as e:
            logging.error(f"Error loading parameter rules: {e}")

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

    def _translate_and_sort_partitions(self, initial_partitions: List[List[int]]) -> List[List[int]]:
        translated_partitions = []
        for partition in initial_partitions:
            if not partition: continue
            new_partition = [self.original_to_new_index_map.get(old_idx) for old_idx in partition]
            if any(idx is None for idx in new_partition): continue
            translated_partitions.append(sorted(new_partition))
        translated_partitions.sort(key=lambda partition: self.raw_logs[partition[0]]['_datetime'] if partition else datetime.max)
        return translated_partitions

    def _translate_back_to_original_indices(self, refined_partitions: List[List[int]]) -> List[List[int]]:
        return [[self.new_to_original_index_map[new_idx] for new_idx in partition] for partition in refined_partitions if partition]

    def _group_partitions_by_day(self, partitions: List[List[int]]) -> Dict[date, List[List[int]]]:
        partitions_by_day: DefaultDict[date, List[List[int]]] = defaultdict(list)
        for partition in partitions:
            if not partition: continue
            partitions_by_day[self.raw_logs[partition[0]]['_datetime'].date()].append(partition)
        return {day: partitions_by_day[day] for day in sorted(partitions_by_day.keys())}
    
    def _get_param_values(self, log_idx: int, keys: List[str]) -> Tuple[Any, ...]:
        log = self.raw_logs[log_idx]
        return tuple(log.get(key) for key in keys)

    def _split_based_on_parameter_rules(self, sessions: List[List[int]]) -> List[List[int]]:
        """
        根据参数规则分裂事件，同时保证时序性并合理处理None日志。
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
            # session 已经是按时间排序的
            if len(session) <= 1:
                if session: final_sessions.append(session)
                continue

            # 1. 根据主属性值对日志进行分组
            groups: Dict[Optional[Tuple], List[int]] = defaultdict(list)
            for log_idx in session:
                primary_values = self._get_param_values(log_idx, primary_keys)
                key = primary_values if not all(v is None for v in primary_values) else None
                groups[key].append(log_idx)

            if len(groups) <= 1 or (None in groups.keys() and len(groups) == 2):
                final_sessions.append(session)
                continue

            # 2. 分裂事件，并分离出主属性为None的日志
            base_sessions = [grp for key, grp in groups.items() if key is not None]
            logs_to_redistribute = groups.get(None, [])

            # 3. 次属性归并：尝试将None日志根据次要属性归并到已分裂的子事件中
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

            # 4. 【新逻辑】处理剩余无法归并的None日志：将它们合并到最大的子事件中
            if logs_to_redistribute and base_sessions:
                # 找到最大的子事件作为“主事件”
                largest_session_idx = max(range(len(base_sessions)), key=lambda i: len(base_sessions[i]))
                # 将无法归并的日志全部并入主事件
                base_sessions[largest_session_idx].extend(logs_to_redistribute)
                # 【关键】合并后必须重新排序以维持时序性
                base_sessions[largest_session_idx].sort()
            elif logs_to_redistribute:
                # 如果分裂后没有base_sessions（所有日志主属性都为None），则它们本身就是一个事件
                final_sessions.append(logs_to_redistribute)

            final_sessions.extend(base_sessions)

        # 5. 【关键】对所有最终生成的事件列表按启动时间进行排序，确保后续步骤的输入是时序正确的
        final_sessions.sort(key=lambda s: s[0] if s else float('inf'))
        
        num_sessions_after = len(final_sessions)
        if num_sessions_before != num_sessions_after:
            logging.debug(f"Parameter-based splitting changed session count from {num_sessions_before} to {num_sessions_after}.")
            
        return final_sessions

    def _check_top_k_belongingness(self, session_indices: List[int]) -> List[bool]:
        session_len = len(session_indices)
        if session_len < 2:
            return [True] * session_len

        # 1. 准备原始数据的 Tensor
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
            
            # --- 分支 A: Transformer 模型 (使用滑动窗口) ---
            if self.is_transformer:
                # 构建 batch 列表，每个元素是截取后的窗口
                batch_templates_list = []
                batch_params_list = []
                batch_mask_indices = []

                for k in range(current_batch_size):
                    target_idx_in_session = start_idx + k
                    
                    # 计算窗口范围：以 target 为中心
                    half_window = self.max_seq_len // 2
                    win_start = max(0, target_idx_in_session - half_window)
                    win_end = min(session_len, win_start + self.max_seq_len)
                    
                    # 如果右边界越界，且左边还有空间，往左移动窗口以填满 max_seq_len
                    if (win_end - win_start) < self.max_seq_len and win_start > 0:
                        win_start = max(0, win_end - self.max_seq_len)
                    
                    # 切片
                    template_slice = original_template_ids[win_start:win_end]
                    param_slice = padded_params[win_start:win_end]
                    
                    # 计算 mask 在切片中的相对位置
                    relative_mask_idx = target_idx_in_session - win_start
                    
                    batch_templates_list.append(template_slice)
                    batch_params_list.append(param_slice)
                    batch_mask_indices.append(relative_mask_idx)

                # Pad batches (因为 Session 头尾的窗口可能不足 max_seq_len)
                batch_template_ids = torch.nn.utils.rnn.pad_sequence(
                    batch_templates_list, batch_first=True, padding_value=self.encoder.template_to_id.get(self.config.PAD_TOKEN, 0)
                )
                batch_param_ids = torch.nn.utils.rnn.pad_sequence(
                    batch_params_list, batch_first=True, padding_value=self.encoder.param_to_id.get(self.config.PAD_TOKEN, 0)
                )
                
                mask_seq_indices = torch.tensor(batch_mask_indices) # 相对位置
                mask_batch_indices = torch.arange(current_batch_size)

            # --- 分支 B: Mamba / RNN 模型 (全量上下文) ---
            else:
                # 保持原有逻辑：直接复制整个 Session
                batch_template_ids = original_template_ids.repeat(current_batch_size, 1)
                batch_param_ids = padded_params.unsqueeze(0).repeat(current_batch_size, 1, 1)
                
                mask_batch_indices = torch.arange(current_batch_size)
                mask_seq_indices = torch.arange(start_idx, end_idx) # 绝对位置

            # --- 公共推理逻辑 ---
            # 应用 Mask
            batch_template_ids[mask_batch_indices, mask_seq_indices] = self.mask_template_id
            
            batch_template_ids = batch_template_ids.to(self.config.device)
            batch_param_ids = batch_param_ids.to(self.config.device)

            with torch.no_grad():
                # Model forward
                mlm_logits, _, _ = self.model(batch_template_ids, batch_param_ids)

            # 获取 Mask 位置的预测结果
            target_logits = mlm_logits[mask_batch_indices, mask_seq_indices, :]
            target_template_ids = original_template_ids[start_idx:end_idx].to(self.config.device)
            
            _, top_k_indices = torch.topk(target_logits, k=self.config.refiner_top_k, dim=-1)
            is_in_top_k_batch = (top_k_indices == target_template_ids.unsqueeze(1)).any(dim=1)
            
            all_is_in_top_k.append(is_in_top_k_batch.cpu())

        final_is_in_top_k = torch.cat(all_is_in_top_k)
        
        # 处理未知模板 (-1)
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
        【V7.1 最终版优化流程】
        执行事件优化，包含参数规则分裂、语义切分和多场景合并。
        """
        logging.info(f"Starting Phase II refinement for {len(initial_sessions)} coarse candidate partitions...")
        
        internal_partitions = self._translate_and_sort_partitions(initial_sessions)
        partitions_grouped_by_day = self._group_partitions_by_day(internal_partitions)
        
        all_refined_sessions_internal = []
        progress_bar = tqdm(partitions_grouped_by_day.items(), desc="Refining Events Day by Day")
        
        for day, daily_sessions in progress_bar:
            progress_bar.set_postfix_str(f"Day {day}, {len(daily_sessions)} sessions")
            
            # 步骤 A: 参数规则分裂 (硬规则优先，已修复时序问题)
            sessions_after_param_split = self._split_based_on_parameter_rules(daily_sessions)
            
            # 步骤 B: 语义切分 (模型软规则，现在输入是时序正确的)
            sessions_after_semantic_split = self._split_based_on_belongingness(sessions_after_param_split)
            
            # 步骤 C: [保障性排序] 再次排序，确保合并逻辑的输入绝对正确
            sessions_after_semantic_split.sort(key=lambda s: s[0] if s else float('inf'))

            # 步骤 D: 多场景合并
            sessions_after_merge = self._merge_adjacent_sessions(sessions_after_semantic_split)
            
            all_refined_sessions_internal.extend(sessions_after_merge)

        all_refined_sessions_internal.sort(key=lambda s: s[0] if s else float('inf'))
        final_sessions_original_idx = self._translate_back_to_original_indices(all_refined_sessions_internal)

        logging.info(f"Phase II refinement complete. Final refined event count: {len(final_sessions_original_idx)}")
        return final_sessions_original_idx
    
