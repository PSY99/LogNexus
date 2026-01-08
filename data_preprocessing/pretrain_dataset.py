#./data_preprocessing/pretrain_dataset.py

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
 as MLM, RPD, ECO preTraintaskprepareprepareDataDataset.
 - EachLogusethreeConvert.
 """
 def __init__(self, config: Config, encoder: UnifiedLogEncoder, raw_logs: list[dict]):
 self.config = config
 self.encoder = encoder
 self.raw_logs = raw_logs
 
 # Get token ID
 self.mask_template_id = self.encoder.template_to_id[self.config.MASK_TOKEN]
 self.pad_template_id = self.encoder.template_to_id.get(self.config.PAD_TOKEN)
 self.pad_param_id = self.encoder.param_to_id.get(self.config.PAD_TOKEN)

 # 1. UseWindowCreateLogcolumn
 self.log_sequences = self._create_sliding_windows(
 raw_logs, self.config.window_size, self.config.step_size
 )
 
 # prepareprepare RPD task“”Parameter
 # wefromallLoginsetallParameter,Used forchange
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
 inLogListuseWindowCreatecolumn.
 """
 sequences = []
 num_logs = len(logs)
 
 # fromindex 0 start, step_size asstepline
 for i in range(0, num_logs - window_size + 1, step_size):
 # ExtractoneWindowSizecolumn
 window = logs[i: i + window_size]
 sequences.append(window)
 
 return sequences

 def __len__(self):
 # DatasetLengthiscolumnCount
 return len(self.log_sequences)

 def __getitem__(self, idx):
 # GetoneWindowGenerate、LengthLogcolumn
 log_sequence = self.log_sequences[idx]

 # initializeUsed forstorecolumnList
 seq_template_ids = []
 seq_param_ids = []
 seq_mlm_labels = []
 seq_rpd_labels = []
 seq_eco_labels = []

 # columninoneLog
 for log_entry in log_sequence:
 original_log = log_entry
 mod_template = original_log['EventTemplate']
 mod_params = copy.deepcopy(original_log.get('Parameters', []))
 
 # initializeCurrentLoglabel
 mlm_label = -100 # CrossEntropyLoss ignore_index
 rpd_label = 0 # 0 table 'correct'
 eco_label = 0 # 0 table 'correct'

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
 # EnsurechangeParameterParametersame
 while replacement_param == original_param and len(self.param_pool) > 1:
 replacement_param = random.choice(self.param_pool)
 
 mod_params[param_idx_to_replace] = replacement_param
 rpd_label = 1 # markeras 'replaced'

 # --- 3. Event (Parameter) Order Corruption (ECO) ---
 if len(set(mod_params)) > 1 and random.random() < 0.5:
 shuffled_params = copy.deepcopy(mod_params)
 # Ensurebackwardsame
 while shuffled_params == mod_params:
 random.shuffle(shuffled_params)
 mod_params = shuffled_params
 eco_label = 1 # markeras 'corrupted'

 # Use encoder fixbackwardsingleLoglineEncode
 encoded_input = self.encoder.encode({
 'EventTemplate': mod_template,
 'Parameters': mod_params
 })
 
 # willEncodeandlabelAddtocolumnListin
 seq_template_ids.append(encoded_input['template_id'])
 seq_param_ids.append(encoded_input['param_ids'])
 seq_mlm_labels.append(mlm_label)
 seq_rpd_labels.append(rpd_label)
 seq_eco_labels.append(eco_label)

 # 【】asWindowEnsureEachSequence lengthis window_size,
 # weneed tolineor.

 # willListConvertasamountReturn
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
 Custom collate functionNumber,willBatchinDictionaryList（EachDictionaryonecolumn）intoBatchamount.
 functionNumberNo.
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
 

