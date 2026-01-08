#./event_refinement/model/bi_directional_log_mamba.py

import os
import torch
import torch.nn as nn

from mamba_ssm import Mamba

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.config import Config

class BiDirectionalLogMamba(nn.Module):
 """
 onebased onBidirectional Mamba LogpreTrainModel,supporthold MLM, RPD, and ECO task.
 
 UseoneForward Mamba andoneBackward Mamba underinfo.
 
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

 # 1. Embeddinglayer (beforesame)
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

 # 2. layer (beforesame)
 self.param_proj = nn.Linear(
 config.max_params * config.mamba_param_embed_dim, 
 config.mamba_d_model
 )
 self.template_proj = nn.Linear(
 config.mamba_template_embed_dim, 
 config.mamba_d_model
 )

 # 3. Mamba coretemplateblock - fixasBidirectional
 # oneForward Mamba andoneBackward Mamba
 # isindependentlytemplateblock,has
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

 # 4. taskOutput - fixBidirectionalOutput
 # aswewillconnectForwardandBackwardOutput,inputDimensionas 2 * d_model
 bidirectional_d_model = 2 * config.mamba_d_model
 self.mlm_head = nn.Linear(bidirectional_d_model, config.template_vocab_size)
 self.rpd_head = nn.Linear(bidirectional_d_model, 1)
 self.eco_head = nn.Linear(bidirectional_d_model, 1)

 def forward(self, template_ids, param_ids):
 """
 Forward
 """
 batch_size, seq_len = template_ids.shape
 
 # 1. GetEmbedding (beforesame)
 template_emb = self.template_embedding(template_ids) 
 param_emb = self.param_embedding(param_ids) 

 # 2. andfusiontogether (beforesame)
 template_proj_emb = self.template_proj(template_emb)
 param_proj_emb = self.param_proj(param_emb.view(batch_size, seq_len, -1))
 combined_input = template_proj_emb + param_proj_emb

 # 3. ThroughBidirectional Mamba core
 # --- Forward ---
 # input: (batch, seq, d_model) -> Output: (batch, seq, d_model)
 fwd_out = self.mamba_fwd(combined_input)

 # --- Backward ---
 # a. willinputcolumnSequence lengthDimensionconvert
 # (batch, seq, d_model) -> (batch, seq, d_model)
 reversed_input = torch.flip(combined_input, dims=[1])
 
 # b. ThroughBackward Mamba
 # (batch, seq, d_model) -> (batch, seq, d_model)
 reversed_out = self.mamba_bwd(reversed_input)
 
 # c. willOutputconvert,column
 # (batch, seq, d_model) -> (batch, seq, d_model)
 bwd_out = torch.flip(reversed_out, dims=[1])
 
 # --- MergeOutput ---
 # willForwardandBackwardOutputinDimensionconnect
 # fwd_out: (batch, seq, d_model)
 # bwd_out: (batch, seq, d_model)
 # mamba_out: (batch, seq, 2 * d_model)
 mamba_out = torch.cat((fwd_out, bwd_out), dim=-1)

 # 4. CalculatetaskOutput (beforeLogicsame,inputDimension)
 # -> (batch, seq, template_vocab_size)
 mlm_logits = self.mlm_head(mamba_out)
 # -> (batch, seq, 1) -> (batch, seq)
 rpd_logits = self.rpd_head(mamba_out).squeeze(-1) 
 # -> (batch, seq, 1) -> (batch, seq)
 eco_logits = self.eco_head(mamba_out).squeeze(-1)

 return mlm_logits, rpd_logits, eco_logits

