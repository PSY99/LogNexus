# -*- coding: utf-8 -*-
# data_preprocessing/dataset.py

import os
import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict, deque
from tqdm import tqdm

import pandas as pd
import torch
from torch.utils.data import Dataset

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.llm_utils import initialize_llm_client, call_llm_api
from event_detector.event_detector import MetaProgrammedDetector
from event_detector.detect_event_baseline import detect_security_events_apache, detect_security_events_Linux, detect_security_events_openssh
from utils.config import Config
from data_preprocessing.log_parser import LogParser, TemplateMatcher

# =================================================================================
# 2. 【New】PredictData (NextTemplateDataset)
# =================================================================================
class BaseDataset(Dataset):
 """
 “Predict”Data.
 - 'train', 'eval', 'online' ,LoadData.
 """
 def __init__(self, config: Config, mode='train', data_source=None):
 self.config = config
 self.mode = mode

 self.client = initialize_llm_client(config)

 if data_source is None:
 data_source = config.data_source_train if mode == 'train' else config.data_source_eval
 logging.info(f"Initializing NextTemplateDataset in '{mode}' mode with data source: '{data_source}'")

 self.raw_logs = []
 self.manual_labels = None
 self.template_matcher = TemplateMatcher(config.template_file_path)
 self.parser = LogParser(self.template_matcher)
 self.num_templates = len(self.template_matcher.template_to_id)

 # LoadSumParseLog ()
 if data_source == 'structured' and mode == 'train':
 structured_df = pd.read_csv(config.train_structured_file_path)
 self.raw_logs = self._parse_from_structured(config.train_origin_log_file_path, structured_df)
 elif data_source == 'structured' and mode == 'online':
 structured_df = pd.read_csv(config.online_structured_file_path)
 self.raw_logs = self._parse_from_structured(config.online_origin_log_file_path, structured_df)
 elif data_source == 'labeled_raw' and mode == 'eval':
 self.raw_logs, self.manual_labels = self._parse_from_labeled_raw(config.label_file_path)
 else:
 raise ValueError(f"Unsupported data source '{data_source}' for mode '{mode}'")
 
 logging.info(f"Total logs parsed: {len(self.raw_logs)}")

 # UseRuleGenerateWindow
 if config.event_detection_strategy == 'rule_based':
 logging.info("Using rule-based event detection.")
 self.sessions, self.log_to_pseudo_label = self._detect_events_baseline(self.raw_logs)
 # UseLLMGenerateWindow
 elif config.event_detection_strategy == 'llm_based':
 logging.info("Using LLM-based event detection.")
 detector = MetaProgrammedDetector(config, self.client)
 # structured_df = pd.read_csv(config.train_structured_file_path)
 # self.raw_logs = self._parse_from_structured(config.train_origin_log_file_path, structured_df)
 self.sessions, self.log_to_pseudo_label = detector.run(self.raw_logs, force_regenerate=False)
 else:
 raise ValueError(f"Unknown event detection strategy: {config.event_detection_strategy}")
 
 logging.info(f"Dataset initialized. Mode: {mode}. Sessions: {len(self.sessions)}.")

 def __len__(self):
 # TrainwhenReturnNumber,EvaluatewhenReturnLogNumber（EvaluateYesLog）
 return len(self.raw_logs)

 def get_sessions_for_eval(self):
 """EvaluatewhenSessionList"""
 return self.sessions
 
 def _parse_log_line(self, line: str, year_context: dict, structured_info=None):
 return self.parser.parse(line, self.config.dataset, year_context, structured_info)

 def _parse_from_structured(self, log_path, structured_df):
 processed_data = []
 year_context = {'prev_year': datetime.now().year, 'prev_month': None}
 with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
 log_lines = f.readlines()
 
 for i, line in enumerate(tqdm(log_lines, desc="Parsing from structured")):
 if i >= len(structured_df):
 break
 structured_info = structured_df.iloc[i]
 parsed_log = self._parse_log_line(line, year_context, structured_info)
 if parsed_log:
 processed_data.append(parsed_log)
 return processed_data

 def _parse_from_labeled_raw(self, path):
 raw_lines, labels = [], []
 cur_label = 0
 with open(path, 'r', encoding="utf-8", errors='ignore') as f:
 for line in f:
 line = line.strip().rstrip("\n")
 if line == "":
 cur_label += 1
 continue
 raw_lines.append(line)
 labels.append(cur_label)

 year_context = {'prev_year': datetime.now().year, 'prev_month': None}
 processed_data, final_labels = [], []
 for i, line in enumerate(tqdm(raw_lines, desc="Parsing from labeled raw")):
 parsed_log = self._parse_log_line(line, year_context)
 if parsed_log:
 processed_data.append(parsed_log)
 final_labels.append(labels[i])
 return processed_data, final_labels
 
 def _detect_events_baseline(self, data):
 if self.config.dataset == "Linux":
 return detect_security_events_Linux(data)
 elif self.config.dataset == "OpenSSH":
 return detect_security_events_openssh(data)
 elif self.config.dataset == "Apache":
 return detect_security_events_apache(data)
 else:
 raise ValueError(f"No specific event detection rule for dataset {self.config.dataset}.")

# =================================================================================
# 3. Number (Used forscriptCall)
# =================================================================================

def get_raw_data_for_fitting(config: Config):
 temp_dataset_shell = BaseDataset.__new__(BaseDataset)
 temp_dataset_shell.parser = LogParser(TemplateMatcher(config.template_file_path))
 temp_dataset_shell.config = config
 temp_dataset_shell.template_matcher = TemplateMatcher(config.template_file_path)

 if config.data_source_train == 'structured':
 structured_df = pd.read_csv(config.train_structured_file_path)
 return temp_dataset_shell._parse_from_structured(config.train_origin_log_file_path, structured_df)
 elif config.data_source_train == 'labeled_raw':
 data, _ = temp_dataset_shell._parse_from_labeled_raw(config.label_file_path)
 return data
 else:
 raise ValueError(f"Unsupported data source for fitting: {config.data_source_train}")
 

