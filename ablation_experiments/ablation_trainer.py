# ablation_experiments/ablation_trainer.py

import os
import logging
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torch.optim import AdamW
from tqdm import tqdm
import sys
import numpy as np

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from data_preprocessing.dataset import get_raw_data_for_fitting
from data_preprocessing.unified_encoder import UnifiedLogEncoder
from data_preprocessing.pretrain_dataset import PretrainDataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AblationTrainer")

def calculate_accuracy(logits, labels, task_type):
    """辅助函数：计算准确率"""
    with torch.no_grad():
        if task_type == 'mlm':
            # MLM: 多分类，忽略 -100
            preds = torch.argmax(logits, dim=-1)
            mask = labels != -100
            if mask.sum() == 0:
                return 0.0
            correct = (preds[mask] == labels[mask]).sum().item()
            total = mask.sum().item()
            return correct / total
        
        elif task_type in ['rpd', 'eco']:
            # 二分类 (BCEWithLogitsLoss)
            probs = torch.sigmoid(logits)
            preds = (probs > 0.5).float()
            correct = (preds == labels).sum().item()
            total = labels.numel()
            return correct / total
    return 0.0

def evaluate_model(model, dataloader, mlm_criterion, rpd_criterion, eco_criterion, config, device, description="Evaluate"):
    """
    评估函数：返回 Loss 和 三个任务的 Accuracy
    """
    model.eval()
    total_loss = 0
    
    mlm_accs = []
    rpd_accs = []
    eco_accs = []

    with torch.no_grad():
        for batch in tqdm(dataloader, desc=description, leave=False):
            template_ids = batch['template_ids'].to(device)
            param_ids = batch['param_ids'].to(device)
            mlm_labels = batch['mlm_labels'].to(device)
            rpd_labels = batch['rpd_labels'].to(device)
            eco_labels = batch['eco_labels'].to(device)

            mlm_logits, rpd_logits, eco_logits = model(template_ids, param_ids)

            # 1. Calculate Loss
            loss_mlm = mlm_criterion(mlm_logits.view(-1, config.template_vocab_size), mlm_labels.view(-1))
            loss_rpd = rpd_criterion(rpd_logits.view(-1), rpd_labels.view(-1))
            loss_eco = eco_criterion(eco_logits.view(-1), eco_labels.view(-1))

            batch_loss = (config.mlm_weight * loss_mlm + 
                          config.rpd_weight * loss_rpd + 
                          config.eco_weight * loss_eco)
            total_loss += batch_loss.item()

            # 2. Calculate Accuracy
            mlm_accs.append(calculate_accuracy(mlm_logits, mlm_labels, 'mlm'))
            rpd_accs.append(calculate_accuracy(rpd_logits, rpd_labels, 'rpd'))
            eco_accs.append(calculate_accuracy(eco_logits, eco_labels, 'eco'))

    metrics = {
        "loss": total_loss / len(dataloader),
        "mlm_acc": np.mean(mlm_accs),
        "rpd_acc": np.mean(rpd_accs),
        "eco_acc": np.mean(eco_accs)
    }
    return metrics

def train_ablation_model(config: Config, model_class, model_name: str, save_path: str):
    """
    训练消融模型，并返回测试集上的指标。
    """
    logger.info(f"[{model_name}] Starting Training Pipeline...")

    # 1. 准备 Encoder
    if os.path.exists(config.encoder_save_path):
        encoder = UnifiedLogEncoder.load(config.encoder_save_path)
    else:
        logger.info("Encoder not found. Fitting a new one...")
        raw_data = get_raw_data_for_fitting(config)
        encoder = UnifiedLogEncoder(config)
        encoder.fit(raw_data)
        encoder.save(config.encoder_save_path)
    
    config.template_vocab_size = encoder.template_vocab_size
    config.param_vocab_size = encoder.param_vocab_size

    # 2. 准备数据
    logger.info(f"[{model_name}] Loading Data...")
    raw_logs = get_raw_data_for_fitting(config)
    full_dataset = PretrainDataset(config, encoder, raw_logs)

    # 划分数据集 (80/10/10)
    train_size = int(0.8 * len(full_dataset))
    val_size = int(0.1 * len(full_dataset))
    test_size = len(full_dataset) - train_size - val_size
    
    # 固定 seed 以保证可复现性
    generator = torch.Generator().manual_seed(42)
    train_dataset, val_dataset, test_dataset = random_split(full_dataset, [train_size, val_size, test_size], generator=generator)

    train_loader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True, collate_fn=PretrainDataset.collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False, collate_fn=PretrainDataset.collate_fn)
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False, collate_fn=PretrainDataset.collate_fn)

    # 3. 初始化模型
    logger.info(f"[{model_name}] Initializing Model...")
    model = model_class(config).to(config.device)
    
    mlm_criterion = nn.CrossEntropyLoss(ignore_index=-100)
    rpd_criterion = nn.BCEWithLogitsLoss()
    eco_criterion = nn.BCEWithLogitsLoss()
    optimizer = AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)

    # 4. 训练循环
    best_val_loss = float('inf')
    epochs = config.epochs 

    for epoch in range(epochs):
        model.train()
        total_train_loss = 0
        
        loop = tqdm(train_loader, desc=f"[{model_name}] Epoch {epoch+1}/{epochs}", leave=False)
        for batch in loop:
            template_ids = batch['template_ids'].to(config.device)
            param_ids = batch['param_ids'].to(config.device)
            mlm_labels = batch['mlm_labels'].to(config.device)
            rpd_labels = batch['rpd_labels'].to(config.device)
            eco_labels = batch['eco_labels'].to(config.device)

            mlm_logits, rpd_logits, eco_logits = model(template_ids, param_ids)

            loss_mlm = mlm_criterion(mlm_logits.view(-1, config.template_vocab_size), mlm_labels.view(-1))
            loss_rpd = rpd_criterion(rpd_logits.view(-1), rpd_labels.view(-1))
            loss_eco = eco_criterion(eco_logits.view(-1), eco_labels.view(-1))

            loss = (config.mlm_weight * loss_mlm + 
                    config.rpd_weight * loss_rpd + 
                    config.eco_weight * loss_eco)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_train_loss += loss.item()
            loop.set_postfix(loss=loss.item())

        # Validation
        val_metrics = evaluate_model(model, val_loader, mlm_criterion, rpd_criterion, eco_criterion, config, config.device, description="Validation")
        avg_val_loss = val_metrics["loss"]
        
        logger.info(f"[{model_name}] Epoch {epoch+1} | Train Loss: {total_train_loss/len(train_loader):.4f} | Val Loss: {avg_val_loss:.4f}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save(model.state_dict(), save_path)
            logger.info(f"[{model_name}] Saved Best Model -> {save_path}")

    # 5. Final Test Evaluation
    logger.info(f"[{model_name}] Loading best model for Test Evaluation...")
    model.load_state_dict(torch.load(save_path, map_location=config.device))
    test_metrics = evaluate_model(model, test_loader, mlm_criterion, rpd_criterion, eco_criterion, config, config.device, description="Testing")
    
    logger.info(f"[{model_name}] Test Metrics: MLM={test_metrics['mlm_acc']:.4f}, RPD={test_metrics['rpd_acc']:.4f}, ECO={test_metrics['eco_acc']:.4f}")
    
    return model, test_metrics

def evaluate_existing_model(config: Config, model, model_name: str):
    """
    如果模型已经存在，直接加载数据并在测试集上跑一次评估，以获取指标。
    """
    logger.info(f"[{model_name}] Evaluating existing model on Test Set...")
    
    # 准备数据 (与训练时逻辑一致)
    if os.path.exists(config.encoder_save_path):
        encoder = UnifiedLogEncoder.load(config.encoder_save_path)
    else:
        # Fallback, shouldn't happen if model exists
        return {}

    raw_logs = get_raw_data_for_fitting(config)
    full_dataset = PretrainDataset(config, encoder, raw_logs)
    
    train_size = int(0.8 * len(full_dataset))
    val_size = int(0.1 * len(full_dataset))
    test_size = len(full_dataset) - train_size - val_size
    
    generator = torch.Generator().manual_seed(42)
    _, _, test_dataset = random_split(full_dataset, [train_size, val_size, test_size], generator=generator)
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False, collate_fn=PretrainDataset.collate_fn)

    mlm_criterion = nn.CrossEntropyLoss(ignore_index=-100)
    rpd_criterion = nn.BCEWithLogitsLoss()
    eco_criterion = nn.BCEWithLogitsLoss()

    test_metrics = evaluate_model(model, test_loader, mlm_criterion, rpd_criterion, eco_criterion, config, config.device, description="Testing Existing Model")
    return test_metrics



