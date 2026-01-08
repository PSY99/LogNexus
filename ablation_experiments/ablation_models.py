import torch
import torch.nn as nn
from mamba_ssm import Mamba
import math

# 引用 Config
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config

class UniDirectionalLogMamba(nn.Module):
    """
    Ablation Model: 单向 Mamba。
    用于证明双向上下文的重要性。
    """
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        
        # Embeddings
        self.template_embedding = nn.Embedding(config.template_vocab_size, config.mamba_template_embed_dim, padding_idx=0)
        self.param_embedding = nn.Embedding(config.param_vocab_size, config.mamba_param_embed_dim, padding_idx=0)
        
        # Projections
        self.param_proj = nn.Linear(config.max_params * config.mamba_param_embed_dim, config.mamba_d_model)
        self.template_proj = nn.Linear(config.mamba_template_embed_dim, config.mamba_d_model)
        
        # Mamba (Single Direction)
        self.mamba = Mamba(
            d_model=config.mamba_d_model,
            d_state=config.mamba_d_state,
            d_conv=config.mamba_d_conv,
            expand=config.mamba_expand,
        )
        
        # Heads
        self.mlm_head = nn.Linear(config.mamba_d_model, config.template_vocab_size)
        self.rpd_head = nn.Linear(config.mamba_d_model, 1)
        self.eco_head = nn.Linear(config.mamba_d_model, 1)

    def forward(self, template_ids, param_ids):
        batch_size, seq_len = template_ids.shape
        
        template_emb = self.template_embedding(template_ids)
        param_emb = self.param_embedding(param_ids)
        
        template_proj_emb = self.template_proj(template_emb)
        param_proj_emb = self.param_proj(param_emb.view(batch_size, seq_len, -1))
        
        combined_input = template_proj_emb + param_proj_emb
        
        # Only Forward
        mamba_out = self.mamba(combined_input)
        
        mlm_logits = self.mlm_head(mamba_out)
        rpd_logits = self.rpd_head(mamba_out).squeeze(-1)
        eco_logits = self.eco_head(mamba_out).squeeze(-1)
        
        return mlm_logits, rpd_logits, eco_logits

class LogTransformer(nn.Module):
    """
    Ablation Model: Transformer Encoder。
    用于证明 Mamba 在长序列上的效率优势（虽然在短序列上 Transformer 效果可能接近）。
    """
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        
        self.template_embedding = nn.Embedding(config.template_vocab_size, config.mamba_template_embed_dim, padding_idx=0)
        self.param_embedding = nn.Embedding(config.param_vocab_size, config.mamba_param_embed_dim, padding_idx=0)
        
        self.param_proj = nn.Linear(config.max_params * config.mamba_param_embed_dim, config.mamba_d_model)
        self.template_proj = nn.Linear(config.mamba_template_embed_dim, config.mamba_d_model)
        
        # Positional Encoding (Required for Transformer)
        self.pos_encoder = PositionalEncoding(config.mamba_d_model, dropout=0.1)
        
        # Transformer Encoder Layer
        encoder_layers = nn.TransformerEncoderLayer(
            d_model=config.mamba_d_model, 
            nhead=4, 
            dim_feedforward=config.mamba_d_model * 4, 
            dropout=0.1,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=4) # 保持层数与 Mamba 规模相当
        
        # Heads (Bidirectional context is inherent in Transformer Encoder with no mask)
        # Output dimension is d_model (not 2*d_model like Bi-Mamba, unless we concat)
        # To make comparison fair, we project to whatever head needs.
        self.mlm_head = nn.Linear(config.mamba_d_model, config.template_vocab_size)
        self.rpd_head = nn.Linear(config.mamba_d_model, 1)
        self.eco_head = nn.Linear(config.mamba_d_model, 1)

    def forward(self, template_ids, param_ids):
        batch_size, seq_len = template_ids.shape
        
        template_emb = self.template_embedding(template_ids)
        param_emb = self.param_embedding(param_ids)
        
        template_proj_emb = self.template_proj(template_emb)
        param_proj_emb = self.param_proj(param_emb.view(batch_size, seq_len, -1))
        
        combined_input = template_proj_emb + param_proj_emb
        combined_input = self.pos_encoder(combined_input)
        
        # Transformer Forward (No mask = Bidirectional)
        trans_out = self.transformer_encoder(combined_input)
        
        mlm_logits = self.mlm_head(trans_out)
        rpd_logits = self.rpd_head(trans_out).squeeze(-1)
        eco_logits = self.eco_head(trans_out).squeeze(-1)
        
        return mlm_logits, rpd_logits, eco_logits

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout=0.1, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x):
        max_len = self.pe.size(0) 
        if x.size(1) > max_len:
            x = x[:, :max_len, :]

        x = x + self.pe[:x.size(1), :]
        return self.dropout(x)


