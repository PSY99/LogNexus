# ./data_preprocessing/pretrain_dataset.py

import os
import random
import copy
import logging

import torch
from torch.utils.data import Dataset

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from data_preprocessing.unified_encoder import UnifiedLogEncoder

class PretrainDataset(Dataset):
    """
    为 MLM, RPD, ECO 预训练任务准备数据的数据集。
    - 对每个日志样本动态应用三种转换。
    """
    def __init__(self, config: Config, encoder: UnifiedLogEncoder, raw_logs: list[dict]):
        self.config = config
        self.encoder = encoder
        self.raw_logs = raw_logs
        
        # 获取特殊 token 的 ID
        self.mask_template_id = self.encoder.template_to_id[self.config.MASK_TOKEN]
        self.pad_template_id = self.encoder.template_to_id.get(self.config.PAD_TOKEN)
        self.pad_param_id = self.encoder.param_to_id.get(self.config.PAD_TOKEN)

        # 1. 使用滑动窗口方法创建日志序列
        self.log_sequences = self._create_sliding_windows(
            raw_logs, self.config.window_size, self.config.step_size
        )
        
        # 准备 RPD 任务所需的“污染”参数池
        # 我们从所有日志中收集所有参数，用于随机替换
        self.param_pool = list(set(
            param for log in raw_logs if log.get('Parameters') for param in log['Parameters']
        ))
        if not self.param_pool:
            logging.warning("Parameter pool for RPD task is empty. RPD will be ineffective.")

        logging.info(f"PretrainDataset initialized with {len(self.raw_logs)} logs.")
        logging.info(f"Window size: {self.config.window_size}, Step size: {self.config.step_size}")
        logging.info(f"RPD parameter pool size: {len(self.param_pool)}")

    def _create_sliding_windows(self, logs: list[dict], window_size: int, step_size: int) -> list[list[dict]]:
        """
        在整个日志列表上应用滑动窗口来创建序列。
        """
        sequences = []
        num_logs = len(logs)
        
        # 从索引 0 开始，以 step_size 为步长进行滑动
        for i in range(0, num_logs - window_size + 1, step_size):
            # 提取一个窗口大小的序列
            window = logs[i : i + window_size]
            sequences.append(window)
            
        return sequences

    def __len__(self):
        # 数据集的长度是序列的数量
        return len(self.log_sequences)

    def __getitem__(self, idx):
        # 获取一个由滑动窗口生成的、固定长度的日志序列
        log_sequence = self.log_sequences[idx]

        # 初始化用于存储整个序列结果的列表
        seq_template_ids = []
        seq_param_ids = []
        seq_mlm_labels = []
        seq_rpd_labels = []
        seq_eco_labels = []

        # 遍历序列中的每一条日志
        for log_entry in log_sequence:
            original_log = log_entry
            mod_template = original_log['EventTemplate']
            mod_params = copy.deepcopy(original_log.get('Parameters', []))
            
            # 初始化当前日志的标签
            mlm_label = -100  # CrossEntropyLoss 的 ignore_index
            rpd_label = 0     # 0 表示 'correct'
            eco_label = 0     # 0 表示 'correct'

            # --- 1. Masked Language Model (MLM) ---
            if random.random() < self.config.mlm_prob:
                mlm_label = self.encoder.template_to_id.get(mod_template, -1)
                if mlm_label == -1:
                    raise ValueError(f"Template '{mod_template}' not found in vocabulary.")
                mod_template = self.config.MASK_TOKEN
            
            # --- 2. Replaced Parameter Detection (RPD) ---
            if len(mod_params) > 0 and self.param_pool and random.random() < self.config.rpd_prob:
                param_idx_to_replace = random.randint(0, len(mod_params) - 1)
                original_param = mod_params[param_idx_to_replace]
                
                replacement_param = original_param
                # 确保替换的参数与原始参数不同
                while replacement_param == original_param and len(self.param_pool) > 1:
                    replacement_param = random.choice(self.param_pool)
                
                mod_params[param_idx_to_replace] = replacement_param
                rpd_label = 1 # 标记为 'replaced'

            # --- 3. Event (Parameter) Order Corruption (ECO) ---
            if len(set(mod_params)) > 1 and random.random() < 0.5:
                shuffled_params = copy.deepcopy(mod_params)
                # 确保打乱后的顺序与原始顺序不同
                while shuffled_params == mod_params:
                    random.shuffle(shuffled_params)
                mod_params = shuffled_params
                eco_label = 1 # 标记为 'corrupted'

            # 使用 encoder 对修改后的单条日志进行编码
            encoded_input = self.encoder.encode({
                'EventTemplate': mod_template,
                'Parameters': mod_params
            })
            
            # 将编码结果和标签添加到序列列表中
            seq_template_ids.append(encoded_input['template_id'])
            seq_param_ids.append(encoded_input['param_ids'])
            seq_mlm_labels.append(mlm_label)
            seq_rpd_labels.append(rpd_label)
            seq_eco_labels.append(eco_label)

        # 【重要】因为滑动窗口确保了每个序列的长度都是 window_size，
        # 所以我们不再需要进行填充或截断。

        # 将列表转换为张量并返回
        return {
            "template_ids": torch.tensor(seq_template_ids, dtype=torch.long),
            "param_ids": torch.stack(seq_param_ids),
            "mlm_labels": torch.tensor(seq_mlm_labels, dtype=torch.long),
            "rpd_labels": torch.tensor(seq_rpd_labels, dtype=torch.float),
            "eco_labels": torch.tensor(seq_eco_labels, dtype=torch.float),
        }

    @staticmethod
    def collate_fn(batch: list[dict]):
        """
        自定义的 collate 函数，将批次中的字典列表（每个字典包含一个序列）堆叠成批次张量。
        这个函数无需改变。
        """
        template_ids_list = [item['template_ids'] for item in batch]
        param_ids_list = [item['param_ids'] for item in batch]
        mlm_labels_list = [item['mlm_labels'] for item in batch]
        rpd_labels_list = [item['rpd_labels'] for item in batch]
        eco_labels_list = [item['eco_labels'] for item in batch]

        return {
            "template_ids": torch.stack(template_ids_list, dim=0),
            "param_ids": torch.stack(param_ids_list, dim=0),
            "mlm_labels": torch.stack(mlm_labels_list, dim=0),
            "rpd_labels": torch.stack(rpd_labels_list, dim=0),
            "eco_labels": torch.stack(eco_labels_list, dim=0),
        }
    

