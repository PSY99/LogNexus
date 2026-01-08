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
    [升级版]
    - 核心功能: 管理模板和参数的词汇表，并将原始日志字典转换为包含 template_id 和 param_ids 的字典。
    - 新增功能: 支持 <CLS> 和 <MASK> 特殊模板Token。
    """
    def __init__(self, cfg=Config):
        self.config = cfg
        
        # --- 参数词汇表 ---
        self.param_to_id = {
            self.config.PAD_TOKEN: 0,
            self.config.UNK_TOKEN: 1,
        }
        self.id_to_param = {v: k for k, v in self.param_to_id.items()}

        # --- 模板词汇表 ---
        self.template_to_id = {
            self.config.PAD_TOKEN: 0,
            # [NEW] 为MLM和ECO任务添加特殊Token
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
        [新增] 从指定的CSV文件中加载日志模板，并构建词汇表。
        CSV文件应包含一个名为 'EventTemplate' 的列。
        """
        logging.info(f"Loading templates from file: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                # 使用 DictReader 可以通过列名直接访问，更健壮
                reader = csv.DictReader(f)
                for row in reader:
                    template = row.get('EventTemplate')
                    if template and template not in self.template_to_id:
                        self.template_to_id[template] = len(self.template_to_id)
            
            self.id_to_template = {v: k for k, v in self.template_to_id.items()}
            logging.info(f"Successfully loaded {len(self.template_to_id) - len(self.id_to_template)} new templates.")
            logging.info(f"Total template vocabulary size is now: {self.template_vocab_size}")

        except FileNotFoundError:
            logging.error(f"Template file not found at: {filepath}. The template vocabulary will be incomplete.")
        except KeyError:
            logging.error(f"The CSV file at {filepath} must contain a header with 'EventTemplate'.")
        except Exception as e:
            logging.error(f"An error occurred while reading the template file: {e}")

    def fit(self, data: list[dict]):
        """
        [已修改] 在训练数据上同时学习模板和参数的词汇表。
        """
        print("Fitting the Unified Encoder on training data...")
        param_word_freq = defaultdict(int)
        
        for log in tqdm(data, desc="Fitting: Building vocabularies"):
            # 统计参数
            for param in log.get('Parameters', []):
                normalized_tokens = self._normalize_and_tokenize_param(param)
                for token in normalized_tokens:
                    param_word_freq[token] += 1
        
        # 构建参数词汇表
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
        [已修改] 将单条日志字典编码为包含 template_id 和 param_ids 的字典。
        这是必要的格式更改，以支持新模型。
        """
        # 编码模板
        template_str = entry.get('EventTemplate', '')
        template_id = self.template_to_id.get(template_str, -1) # 使用-1表示未找到，后续应过滤

        # 2. 根据 include_params 标志处理参数
        if not include_params:
            # 如果不包含参数，创建一个全为 PAD 的张量并直接返回
            pad_id = self.param_to_id.get(self.config.PAD_TOKEN, 0)
            param_ids_vector = torch.full((self.config.max_params,), pad_id, dtype=torch.long)
        else:
            # 如果包含参数，调用内部方法进行正常编码
            param_ids_vector = self._encode_params(entry)
        
        return {'template_id': template_id, 'param_ids': param_ids_vector}

    def _encode_params(self, entry: dict) -> torch.Tensor:
        """
        将日志的参数编码为ID序列。
        (此部分逻辑基本源自您的代码，移除了IP和PID的特殊处理，简化为统一参数)
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
            return ['<IP_ADDR>'] # 统一IP表示
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
    



    