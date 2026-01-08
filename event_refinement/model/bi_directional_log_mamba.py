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
 onebased onBidirectional Mamba LogpreTrainModel,support持 MLM, RPD, and ECO task.
 
 它UseoneForward Mamba andoneBackward Mamba 来捕捉完整上下文info.
 
 input:
 - template_ids: (batch_size, seq_len)
 - param_ids: (batch_size, seq_len, max_params)
 
 Output:
 - mlm_logits: (batch_size, seq_len, template_vocab_size)
 - rpd_logits: (batch_size, seq_len)
 - eco_logits: (batch_size, seq_len)
 """
 def __init__(self, config: Config):
 super().__init__()
 if Mamba is None:
 raise Importerror("mamba_ssm is not installed. Please install it to use BiDirectionalLogMamba.")
 
 self.config = config

 # 1. Embedding层 (与before相same)
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

 # 2. 投影层 (与before相same)
 self.param_proj = nn.Linear(
 config.max_params * config.mamba_param_embed_dim, 
 config.mamba_d_model
 )
 self.template_proj = nn.Linear(
 config.mamba_template_embed_dim, 
 config.mamba_d_model
 )

 # 3. Mamba core模块 - 修改asBidirectional
 # 实例化oneForward Mamba andoneBackward Mamba
 # 它们is两独立模块,拥has各自权重
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

 # 4. taskOutput头 - 修改以适应BidirectionalOutput
 # 因aswewill拼接ForwardandBackwardOutput,所以inputDimension变as 2 * d_model
 bidirectional_d_model = 2 * config.mamba_d_model
 self.mlm_head = nn.Linear(bidirectional_d_model, config.template_vocab_size)
 self.rpd_head = nn.Linear(bidirectional_d_model, 1)
 self.eco_head = nn.Linear(bidirectional_d_model, 1)

 def forward(self, template_ids, param_ids):
 """
 Forward传播
 """
 batch_size, seq_len = template_ids.shape
 
 # 1. GetEmbedding (与before相same)
 template_emb = self.template_embedding(template_ids) 
 param_emb = self.param_embedding(param_ids) 

 # 2. 投影and融合 (与before相same)
 template_proj_emb = self.template_proj(template_emb)
 param_proj_emb = self.param_proj(param_emb.view(batch_size, seq_len, -1))
 combined_input = template_proj_emb + param_proj_emb

 # 3. ThroughBidirectional Mamba core
 # --- Forward传播 ---
 # input: (batch, seq, d_model) -> Output: (batch, seq, d_model)
 fwd_out = self.mamba_fwd(combined_input)

 # --- Backward传播 ---
 # a. willinput序column沿着Sequence lengthDimension反转
 # (batch, seq, d_model) -> (batch, seq, d_model)
 reversed_input = torch.flip(combined_input, dims=[1])
 
 # b. ThroughBackward Mamba
 # (batch, seq, d_model) -> (batch, seq, d_model)
 reversed_out = self.mamba_bwd(reversed_input)
 
 # c. willOutput反转回来,使其与原始序column顺序对齐
 # (batch, seq, d_model) -> (batch, seq, d_model)
 bwd_out = torch.flip(reversed_out, dims=[1])
 
 # --- MergeOutput ---
 # willForwardandBackwardOutputin特征Dimension上拼接
 # fwd_out: (batch, seq, d_model)
 # bwd_out: (batch, seq, d_model)
 # mamba_out: (batch, seq, 2 * d_model)
 mamba_out = torch.cat((fwd_out, bwd_out), dim=-1)

 # 4. Calculate各taskOutput (与beforeLogic相same,但inputDimension变)
 # -> (batch, seq, template_vocab_size)
 mlm_logits = self.mlm_head(mamba_out)
 # -> (batch, seq, 1) -> (batch, seq)
 rpd_logits = self.rpd_head(mamba_out).squeeze(-1) 
 # -> (batch, seq, 1) -> (batch, seq)
 eco_logits = self.eco_head(mamba_out).squeeze(-1)

 return mlm_logits, rpd_logits, eco_logits


