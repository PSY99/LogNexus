# ./event_refinement/model/bi_directional_log_mamba.py

import os
import torch
import torch.nn as nn

from mamba_ssm import Mamba

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.config import Config


class BiDirectionalLogMamba(nn.Module):
    """
    一个基于双向 Mamba 的日志预训练模型，支持 MLM, RPD, 和 ECO 任务。
    
    它使用一个前向 Mamba 和一个后向 Mamba 来捕捉完整的上下文信息。
    
    输入:
    - template_ids: (batch_size, seq_len)
    - param_ids: (batch_size, seq_len, max_params)
    
    输出:
    - mlm_logits: (batch_size, seq_len, template_vocab_size)
    - rpd_logits: (batch_size, seq_len)
    - eco_logits: (batch_size, seq_len)
    """
    def __init__(self, config: Config):
        super().__init__()
        if Mamba is None:
            raise ImportError("mamba_ssm is not installed. Please install it to use BiDirectionalLogMamba.")
            
        self.config = config

        # 1. 嵌入层 (与之前相同)
        self.template_embedding = nn.Embedding(
            config.template_vocab_size, 
            config.mamba_template_embed_dim, 
            padding_idx=0
        )
        self.param_embedding = nn.Embedding(
            config.param_vocab_size, 
            config.mamba_param_embed_dim, 
            padding_idx=0
        )

        # 2. 投影层 (与之前相同)
        self.param_proj = nn.Linear(
            config.max_params * config.mamba_param_embed_dim, 
            config.mamba_d_model
        )
        self.template_proj = nn.Linear(
            config.mamba_template_embed_dim, 
            config.mamba_d_model
        )

        # 3. Mamba 核心模块 - 修改为双向
        # 实例化一个前向 Mamba 和一个后向 Mamba
        # 它们是两个独立的模块，拥有各自的权重
        self.mamba_fwd = Mamba(
            d_model=config.mamba_d_model,
            d_state=config.mamba_d_state,
            d_conv=config.mamba_d_conv,
            expand=config.mamba_expand,
        )
        self.mamba_bwd = Mamba(
            d_model=config.mamba_d_model,
            d_state=config.mamba_d_state,
            d_conv=config.mamba_d_conv,
            expand=config.mamba_expand,
        )

        # 4. 任务输出头 - 修改以适应双向输出
        # 因为我们将拼接前向和后向的输出，所以输入维度变为 2 * d_model
        bidirectional_d_model = 2 * config.mamba_d_model
        self.mlm_head = nn.Linear(bidirectional_d_model, config.template_vocab_size)
        self.rpd_head = nn.Linear(bidirectional_d_model, 1)
        self.eco_head = nn.Linear(bidirectional_d_model, 1)

    def forward(self, template_ids, param_ids):
        """
        前向传播
        """
        batch_size, seq_len = template_ids.shape
        
        # 1. 获取嵌入 (与之前相同)
        template_emb = self.template_embedding(template_ids) 
        param_emb = self.param_embedding(param_ids) 

        # 2. 投影和融合 (与之前相同)
        template_proj_emb = self.template_proj(template_emb)
        param_proj_emb = self.param_proj(param_emb.view(batch_size, seq_len, -1))
        combined_input = template_proj_emb + param_proj_emb

        # 3. 通过双向 Mamba 核心
        # --- 前向传播 ---
        # 输入: (batch, seq, d_model) -> 输出: (batch, seq, d_model)
        fwd_out = self.mamba_fwd(combined_input)

        # --- 后向传播 ---
        # a. 将输入序列沿着序列长度维度反转
        # (batch, seq, d_model) -> (batch, seq, d_model)
        reversed_input = torch.flip(combined_input, dims=[1])
        
        # b. 通过后向 Mamba
        # (batch, seq, d_model) -> (batch, seq, d_model)
        reversed_out = self.mamba_bwd(reversed_input)
        
        # c. 将输出反转回来，使其与原始序列顺序对齐
        # (batch, seq, d_model) -> (batch, seq, d_model)
        bwd_out = torch.flip(reversed_out, dims=[1])
        
        # --- 合并输出 ---
        # 将前向和后向的输出在特征维度上拼接
        # fwd_out: (batch, seq, d_model)
        # bwd_out: (batch, seq, d_model)
        # mamba_out: (batch, seq, 2 * d_model)
        mamba_out = torch.cat((fwd_out, bwd_out), dim=-1)

        # 4. 计算各任务的输出 (与之前逻辑相同，但输入维度变了)
        # -> (batch, seq, template_vocab_size)
        mlm_logits = self.mlm_head(mamba_out)
        # -> (batch, seq, 1) -> (batch, seq)
        rpd_logits = self.rpd_head(mamba_out).squeeze(-1) 
        # -> (batch, seq, 1) -> (batch, seq)
        eco_logits = self.eco_head(mamba_out).squeeze(-1)

        return mlm_logits, rpd_logits, eco_logits


