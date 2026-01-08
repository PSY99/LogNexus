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
 as MLM, RPD, ECO preTraintaskprepare备DataDataset.
 - 对EachLog样本动态应用three种Convert.
 """
 def __init__(self, config: Config, encoder: UnifiedLogEncoder, raw_logs: list[dict]):
 self.config = config
 self.encoder = encoder
 self.raw_logs = raw_logs
 
 # Get特殊 token ID
 self.mask_template_id = self.encoder.template_to_id[self.config.MASK_TOKEN]
 self.pad_template_id = self.encoder.template_to_id.get(self.config.PAD_TOKEN)
 self.pad_param_id = self.encoder.param_to_id.get(self.config.PAD_TOKEN)

 # 1. Use滑动Window方法CreateLog序column
 self.log_sequences = self._create_sliding_windows(
 raw_logs, self.config.window_size, self.config.step_size
 )
 
 # prepare备 RPD task所需“污染”Parameter池
 # wefromallLogin收setallParameter,Used for随机替换
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
 in整LogList上应用滑动Window来Create序column.
 """
 sequences = []
 num_logs = len(logs)
 
 # fromindex 0 start,以 step_size asstep长进line滑动
 for i in range(0, num_logs - window_size + 1, step_size):
 # ExtractoneWindowSize序column
 window = logs[i : i + window_size]
 sequences.append(window)
 
 return sequences

 def __len__(self):
 # DatasetLengthis序columnCount
 return len(self.log_sequences)

 def __getitem__(self, idx):
 # Getone由滑动WindowGenerate、固定LengthLog序column
 log_sequence = self.log_sequences[idx]

 # initializeUsed for存储整序column结果List
 seq_template_ids = []
 seq_param_ids = []
 seq_mlm_labels = []
 seq_rpd_labels = []
 seq_eco_labels = []

 # 遍历序columnin每one条Log
 for log_entry in log_sequence:
 original_log = log_entry
 mod_template = original_log['EventTemplate']
 mod_params = copy.deepcopy(original_log.get('Parameters', []))
 
 # initializeCurrentLoglabel
 mlm_label = -100 # CrossEntropyLoss ignore_index
 rpd_label = 0 # 0 table示 'correct'
 eco_label = 0 # 0 table示 'correct'

 # --- 1. Masked Language Model (MLM) ---
 if random.random() < self.config.mlm_prob:
 mlm_label = self.encoder.template_to_id.get(mod_template, -1)
 if mlm_label == -1:
 raise Valueerror(f"Template '{mod_template}' not found in vocabulary.")
 mod_template = self.config.MASK_TOKEN
 
 # --- 2. Replaced Parameter Detection (RPD) ---
 if len(mod_params) > 0 and self.param_pool and random.random() < self.config.rpd_prob:
 param_idx_to_replace = random.randint(0, len(mod_params) - 1)
 original_param = mod_params[param_idx_to_replace]
 
 replacement_param = original_param
 # Ensure替换Parameter与原始Parameter不same
 while replacement_param == original_param and len(self.param_pool) > 1:
 replacement_param = random.choice(self.param_pool)
 
 mod_params[param_idx_to_replace] = replacement_param
 rpd_label = 1 # markeras 'replaced'

 # --- 3. Event (Parameter) Order Corruption (ECO) ---
 if len(set(mod_params)) > 1 and random.random() < 0.5:
 shuffled_params = copy.deepcopy(mod_params)
 # Ensure打乱后顺序与原始顺序不same
 while shuffled_params == mod_params:
 random.shuffle(shuffled_params)
 mod_params = shuffled_params
 eco_label = 1 # markeras 'corrupted'

 # Use encoder 对修改后single条Log进lineEncode
 encoded_input = self.encoder.encode({
 'EventTemplate': mod_template,
 'Parameters': mod_params
 })
 
 # willEncode结果andlabelAddto序columnListin
 seq_template_ids.append(encoded_input['template_id'])
 seq_param_ids.append(encoded_input['param_ids'])
 seq_mlm_labels.append(mlm_label)
 seq_rpd_labels.append(rpd_label)
 seq_eco_labels.append(eco_label)

 # 【重要】因as滑动WindowEnsureEachSequence length都is window_size,
 # 所以we不再need to进line填充or截断.

 # willListConvertas张量并Return
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
 Custom collate functionNumber,willBatchinDictionaryList（EachDictionary包含one序column）堆叠成Batch张量.
 这functionNumberNo需改变.
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
 

