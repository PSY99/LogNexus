# data_preprocessing/unified_encoder.py

import os
import pickle
import re
import csv
import logging
from collections import defaultdict
from tqdm import tqdm
import torch

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config

class UnifiedLogEncoder:
 """
 [upgraded]
 - coreability: templateboardandParameterVocabularytable,willLogDictionaryConvertas template_id and param_ids Dictionary.
 - Newnewability: supporthold <CLS> and <MASK> templateboardtoken.
 """
 def __init__(self, cfg=Config):
 self.config = cfg
 
 # --- ParameterVocabularytable ---
 self.param_to_id = {
 self.config.PAD_TOKEN: 0,
 self.config.UNK_TOKEN: 1,
 }
 self.id_to_param = {v: k for k, v in self.param_to_id.items()}

 # --- templateboardVocabularytable ---
 self.template_to_id = {
 self.config.PAD_TOKEN: 0,
 # [NEW] asMLMandECOtaskAddtoken
 self.config.CLS_TOKEN: 1,
 self.config.MASK_TOKEN: 2,
 }
 self.id_to_template = {v: k for k, v in self.template_to_id.items()}

 self._load_templates_from_file(self.config.template_file_path)

 @property
 def param_vocab_size(self):
 return len(self.param_to_id)

 @property
 def template_vocab_size(self):
 return len(self.template_to_id)

 def _load_templates_from_file(self, filepath: str):
 """
 [Newnew] fromspecifyCSVFileinLoadLog template,BuildVocabularytable.
 CSVFileonenameas 'EventTemplate' column.
 """
 logging.info(f"Loading templates from file: {filepath}")
 try:
 with open(filepath, 'r', encoding='utf-8') as f:
 # Use DictReader Throughcolumnnamedirectly,
 reader = csv.DictReader(f)
 for row in reader:
 template = row.get('EventTemplate')
 if template and template not in self.template_to_id:
 self.template_to_id[template] = len(self.template_to_id)
 
 self.id_to_template = {v: k for k, v in self.template_to_id.items()}
 logging.info(f"Successfully loaded {len(self.template_to_id) - len(self.id_to_template)} new templates.")
 logging.info(f"total template vocabulary size is now: {self.template_vocab_size}")

 except FileNotFounderror:
 logging.error(f"Template file not found at: {filepath}. The template vocabulary will be incomplete.")
 except Keyerror:
 logging.error(f"The CSV file at {filepath} must contain a header with 'EventTemplate'.")
 except Exception as e:
 logging.error(f"An error occurred while reading the template file: {e}")

 def fit(self, data: list[dict]):
 """
 [fix] inTrainDatasamewhentemplateboardandParameterVocabularytable.
 """
 print("Fitting the Unified Encoder on training data...")
 param_word_freq = defaultdict(int)
 
 for log in tqdm(data, desc="Fitting: Building vocabularies"):
 # StatisticsParameter
 for param in log.get('Parameters', []):
 normalized_tokens = self._normalize_and_tokenize_param(param)
 for token in normalized_tokens:
 param_word_freq[token] += 1
 
 # BuildParameterVocabularytable
 min_freq = self.config.min_param_freq
 max_size = self.config.max_vocab_size
 
 sorted_words = sorted(param_word_freq.items(), key=lambda x: x[1], reverse=True)
 vocab_candidates = [word for word, freq in sorted_words if freq >= min_freq]
 vocab_candidates = vocab_candidates[:max_size - len(self.param_to_id)]
 
 for param in vocab_candidates:
 if param not in self.param_to_id:
 self.param_to_id[param] = len(self.param_to_id)
 self.id_to_param = {v: k for k, v in self.param_to_id.items()}

 print(f"Fitting complete. Template vocab size: {self.template_vocab_size}, Param vocab size: {self.param_vocab_size}")

 def encode(self, entry: dict, include_params: bool = True) -> dict:
 """
 [fix] willsingleLogDictionaryEncodeas template_id and param_ids Dictionary.
 is,supportholdNewModel.
 """
 # Encodetemplateboard
 template_str = entry.get('EventTemplate', '')
 template_id = self.template_to_id.get(template_str, -1) # Use-1tableto,backwardFilter

 # 2. According to include_params markprocessParameter
 if not include_params:
 # IfParameter,Createoneas PAD amountdirectlyReturn
 pad_id = self.param_to_id.get(self.config.PAD_TOKEN, 0)
 param_ids_vector = torch.full((self.config.max_params,), pad_id, dtype=torch.long)
 else:
 # IfParameter,CallinsidelinepositiveEncode
 param_ids_vector = self._encode_params(entry)
 
 return {'template_id': template_id, 'param_ids': param_ids_vector}

 def _encode_params(self, entry: dict) -> torch.Tensor:
 """
 willLog parametersEncodeasIDcolumn.
 (thissplitLogiccode,RemoveIPandPIDprocess,asoneParameter)
 """
 all_tokens = []
 for param in entry.get('Parameters', []):
 all_tokens.extend(self._normalize_and_tokenize_param(param))

 unk_id = self.param_to_id[self.config.UNK_TOKEN]
 param_ids = [self.param_to_id.get(token, unk_id) for token in all_tokens]
 
 max_len = self.config.max_params
 if len(param_ids) > max_len:
 param_ids = param_ids[:max_len]
 else:
 pad_id = self.param_to_id[self.config.PAD_TOKEN]
 param_ids.extend([pad_id] * (max_len - len(param_ids)))
 
 return torch.tensor(param_ids, dtype=torch.long)

 def _normalize_and_tokenize_param(self, param: str) -> list[str]:
 param = str(param)
 if re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', param):
 return ['<IP_ADDR>'] # oneIPtable
 if re.search(r'\d{2}:\d{2}:\d{2}', param):
 return []
 if re.fullmatch(r'0x[0-9a-fA-F]+', param, re.IGNORECASE) or re.fullmatch(r'[+-]?\d+(\.\d+)?', param):
 return ['<NUM>']
 return [param.lower()]

 def save(self, filepath: str):
 with open(filepath, 'wb') as f:
 pickle.dump(self, f)
 print(f"Unified Encoder state saved to {filepath}")

 @staticmethod
 def load(filepath: str):
 with open(filepath, 'rb') as f:
 encoder = pickle.load(f)
 print(f"Unified Encoder state loaded from {filepath}")
 return encoder
 

 