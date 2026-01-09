# utils/config.py

import os
import logging

import torch


class Config:
    """
    Configuration class for the model, training, and data paths.
    """
    def __init__(self):
        self.device = torch.device('cuda:2' if torch.cuda.is_available() else 'cpu')
        self.dataset = os.getenv('DATASET_NAME', "Linux")   # OpenSSH, Linux, Apache

        # LLM api config
        self.llm_api_key = os.getenv("LLM_PROXY_API_KEY", "your_api_key")
        self.llm_model_name = "your_model_name"
        self.llm_base_url = "your_model_url"
        
        self.llm_api_retries = 5
        self.llm_api_timeout = 1200


        # Path configuration
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.dataset_dir = os.path.join(self.project_dir, 'data', self.dataset)
        self.logs_save_dir = os.path.join(self.project_dir, 'logs', self.dataset)
        os.makedirs(self.logs_save_dir, exist_ok=True)

        self.model_save_dir = os.path.join(self.project_dir, 'cache', self.dataset)
        os.makedirs(self.model_save_dir, exist_ok=True)

        self.train_origin_log_file_path = os.path.join(self.dataset_dir, self.dataset + '_train.log')
        self.train_structured_file_path = os.path.join(self.dataset_dir, self.dataset + '.log_structured_train.csv')  

        self.label_file_path = os.path.join(self.dataset_dir, self.dataset + '_test_label.log')

        self.online_origin_log_file_path = os.path.join(self.dataset_dir, self.dataset + '_online_eval.log')
        self.online_structured_file_path = os.path.join(self.dataset_dir, self.dataset + '.log_structured_online_eval.csv')  

        self.template_file_path = os.path.join(self.dataset_dir, self.dataset + '_full.log_templates.csv')
        self.log_structures_path = os.path.join(self.project_dir, 'event_detector', 'log_structures.json')


        # event processing config
        self.event_detection_strategy = 'llm_based'

        artifacts_base_dir = os.path.join(self.project_dir, 'generated_processors')
        artifacts_suffix = os.getenv('ARTIFACTS_SUFFIX', self.dataset)
        self.artifacts_dir = os.path.join(artifacts_base_dir, artifacts_suffix)


        self.sampled_logs_path = os.path.join(self.artifacts_dir, 'sampled_logs.jsonl')
        self.nl_rules_path = os.path.join(self.artifacts_dir, 'natural_language_rules.json')
        self.rule_functions_dir = os.path.join(self.artifacts_dir, 'rule_functions')
        self.event_processor_path = os.path.join(self.artifacts_dir, f'processor_{self.dataset}.py')

        os.makedirs(self.artifacts_dir, exist_ok=True)
        os.makedirs(self.rule_functions_dir, exist_ok=True)

        self.result_dir = os.path.join(self.project_dir, 'results', self.dataset)
        os.makedirs(self.result_dir, exist_ok=True)

        self.detector_sample_size = 500
        self.detector_session_gap_seconds = 600
        self.detector_hotspot_novelty_threshold = 0.0



        # data refinement config
        self.data_source_train = 'structured'
        self.data_source_eval = 'labeled_raw'
        self.data_source_online = 'structured'
        self.param_vocab_size = None
        self.num_templates = None
        self.min_param_freq = 10
        self.max_vocab_size = 10000


        self.batch_size = 32
        self.epochs = 200
        self.learning_rate = 1e-4
        self.weight_decay = 1e-5
        self.eval_interval_steps = 10
        self.dropout_rate = 0.1
        self.max_context_len = 40


        self.template_vocab_size = None
        self.param_vocab_size = None
        self.num_templates = None
        self.template_vector_file_path = os.path.join(self.dataset_dir, f'{self.dataset}_template_vector_pretrained.pt')
        self.predictor_model_name = f"{self.dataset}_NextTemplatePredictor"
        self.predictor_model_path = os.path.join(self.model_save_dir, f'model_{self.predictor_model_name}.pt')
        self.template_embedding_dim = 128
        self.gru_hidden_dim = 256
        self.gru_num_layers = 2
        self.refinement_top_k = 20
        self.pid_consolidation_window_seconds = 12 * 60 * 60
        self.rule_based_events_output_path = os.path.join(self.artifacts_dir, f'events_rules_{self.dataset}.log')
        self.final_events_output_path = os.path.join(self.artifacts_dir, f'events_refined_{self.dataset}.log')



        # ========================================================================
        # --- LogBERT-Mamba 预训练配置 ---
        # ========================================================================

        # 新的统一编码器路径
        self.encoder_save_path = os.path.join(self.model_save_dir, f'{self.dataset}_encoder.pkl')
        # 新的Mamba预训练模型路径
        self.mamba_model_save_path = os.path.join(self.model_save_dir, 'log_mamba_pretrained.pt')

        # 2. 数据与任务配置
        self.max_params = 16  # 单个日志的最大参数token数 (可按需调整)
        
        # 特殊Token定义
        self.PAD_TOKEN = "<PAD>"
        self.UNK_TOKEN = "<UNK>"
        self.CLS_TOKEN = "<CLS>"
        self.MASK_TOKEN = "<MASK>"

        # 预训练任务概率
        self.mlm_prob = 0.15      # 15%的日志模板将被掩码
        self.rpd_prob = 0.15      # 15%的日志参数将被替换
        
        # 预训练损失权重
        self.mlm_weight = 1.0
        self.rpd_weight = 0.5
        self.eco_weight = 0.5

        # 3. Mamba 模型架构配置
        self.mamba_d_model = 256        # 主模型维度
        self.mamba_template_embed_dim = 128 # Mamba模型中的模板嵌入维度
        self.mamba_param_embed_dim = 128    # Mamba模型中的参数嵌入维度
        
        # Mamba-specific
        self.mamba_d_state = 16
        self.mamba_d_conv = 4
        self.mamba_expand = 2

        # --- 数据集和序列化配置 ---
        self.window_size = 32  # 每个训练样本的序列长度
        self.step_size = 16    # 滑动窗口的步长。建议为 window_size 的一半或更小
        self.max_params = 10    # 每条日志允许的最大参数数量


        self.refiner_top_k = 5
        self.refiner_batch_size = 32
        self.refiner_merge_absolute_threshold = 0.8 # 例如，要求合并后至少80%的日志是连贯的
        self.refiner_merge_degradation_allowance = 0.05 # 例如，允许相干性下降最多10%
        self.refiner_merge_time_threshold_minutes = 10  # 10分钟

        self.parameter_rules_path = os.path.join(self.project_dir, 'event_refinement', 'parameter_rules.json')


        # 【新增】相干性阈值：如果一个事件的初始相干性得分高于此值，则跳过对其的切分
        self.COHERENCE_THRESHOLD_TO_SKIP_SPLIT = 0.90

        # 【新增】豁免规则：PID一致性
        # 如果为 True，则 PID 完全一致的事件将被豁免，不进行切分
        self.EXEMPT_IF_PID_CONSISTENT = True

        # 【新增】豁免规则：时间跨度
        # 如果事件内所有日志的时间跨度小于此值（秒），则豁免切分。设为0或负数可禁用。
        self.EXEMPT_IF_TIMESPAN_LESS_THAN_S = 1.0

        # 【新增】合并规则：相同内容日志的时间窗口
        # 如果多个单日志事件的 'Content' 字段完全相同，且它们之间的时间差
        # 小于此值（秒），它们将被合并。设为0或负数可禁用此规则。
        self.MERGE_IDENTICAL_CONTENT_WINDOW_S = 5.0 



        self.kb_cosine_similarity_threshold = 0.7
        self.kb_embedding_sample_size = 100
        self.kb_llm_update_threshold = 20
        self.kb_dir = os.path.join(self.result_dir, "knowledge_base")



