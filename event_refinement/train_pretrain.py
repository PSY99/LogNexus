# ./event_refinement/train_pretrain.py

import os
import logging

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torch.optim import AdamW
from tqdm import tqdm
import swanlab

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from data_preprocessing.dataset import get_raw_data_for_fitting
from data_preprocessing.unified_encoder import UnifiedLogEncoder
from data_preprocessing.pretrain_dataset import PretrainDataset
from event_refinement.model.bi_directional_log_mamba import BiDirectionalLogMamba

# --- 【新增】评估函数，用于验证和测试 ---
def evaluate_model(model, dataloader, mlm_criterion, rpd_criterion, eco_criterion, config, device, description="Evaluate"):
    """
    在给定的数据集上评估模型性能。
    此函数被重构出来，用于验证集和测试集，以避免代码重复。

    Args:
        model (nn.Module): 要评估的模型。
        dataloader (DataLoader): 数据加载器 (验证或测试)。
        mlm_criterion, rpd_criterion, eco_criterion: 损失函数。
        config (Config): 配置对象。
        device (torch.device): 'cuda' or 'cpu'。
        description (str): tqdm 进度条的描述文字。

    Returns:
        dict: 包含平均损失和各项准确率的字典。
    """
    model.eval()
    
    total_loss = 0
    total_mlm_correct, total_mlm_count = 0, 0
    total_rpd_correct, total_rpd_count = 0, 0
    total_eco_correct, total_eco_count = 0, 0

    with torch.no_grad():
        for batch in tqdm(dataloader, desc=description):
            template_ids = batch['template_ids'].to(device)
            param_ids = batch['param_ids'].to(device)
            mlm_labels = batch['mlm_labels'].to(device)
            rpd_labels = batch['rpd_labels'].to(device)
            eco_labels = batch['eco_labels'].to(device)

            mlm_logits, rpd_logits, eco_logits = model(template_ids, param_ids)

            loss_mlm = mlm_criterion(mlm_logits.view(-1, config.template_vocab_size), mlm_labels.view(-1))
            loss_rpd = rpd_criterion(rpd_logits.view(-1), rpd_labels.view(-1))
            loss_eco = eco_criterion(eco_logits.view(-1), eco_labels.view(-1))

            batch_loss = (config.mlm_weight * loss_mlm + 
                          config.rpd_weight * loss_rpd + 
                          config.eco_weight * loss_eco)
            
            total_loss += batch_loss.item()

            # 计算准确率
            # MLM 准确率
            mlm_mask = mlm_labels != -100
            if mlm_mask.sum() > 0:
                mlm_preds = torch.argmax(mlm_logits, dim=-1)
                total_mlm_correct += (mlm_preds[mlm_mask] == mlm_labels[mlm_mask]).sum().item()
                total_mlm_count += mlm_mask.sum().item()
            
            # RPD 准确率
            rpd_preds = (rpd_logits > 0).float()
            total_rpd_correct += (rpd_preds == rpd_labels).sum().item()
            total_rpd_count += rpd_labels.numel()

            # ECO 准确率
            eco_preds = (eco_logits > 0).float()
            total_eco_correct += (eco_preds == eco_labels).sum().item()
            total_eco_count += eco_labels.numel()

    avg_loss = total_loss / len(dataloader)
    avg_mlm_acc = total_mlm_correct / total_mlm_count if total_mlm_count > 0 else 0
    avg_rpd_acc = total_rpd_correct / total_rpd_count if total_rpd_count > 0 else 0
    avg_eco_acc = total_eco_correct / total_eco_count if total_eco_count > 0 else 0

    return {
        "loss": avg_loss,
        "mlm_acc": avg_mlm_acc,
        "rpd_acc": avg_rpd_acc,
        "eco_acc": avg_eco_acc
    }

def pretrain_model(config: Config):
    """
    执行 LogMamba 模型的预训练流程 (MLM, RPD, ECO)，并在独立的测试集上评估最终模型。
    """
    logging.info("Running in PRE-TRAIN mode for LogMamba.")
    swanlab.init(
        project="LogEvent-Pretrain1", 
        experiment_name=f"LogMamba_{config.dataset}_bi", 
        config=config.__dict__
    )

    # --- 1. 准备编码器 (Encoder) ---
    logging.info("Preparing UnifiedLogEncoder...")
    if os.path.exists(config.encoder_save_path):
        encoder = UnifiedLogEncoder.load(config.encoder_save_path)
    else:
        logging.info("Encoder not found. Fitting a new one...")
        raw_data_for_fit = get_raw_data_for_fitting(config)
        encoder = UnifiedLogEncoder(config)
        encoder.fit(raw_data_for_fit)
        encoder.save(config.encoder_save_path)
    
    config.template_vocab_size = encoder.template_vocab_size
    config.param_vocab_size = encoder.param_vocab_size
    logging.info(f"Encoder ready. Template vocab: {config.template_vocab_size}, Param vocab: {config.param_vocab_size}")

    # --- 2. 准备数据集 (Dataset) ---
    logging.info("Loading raw data for pre-training...")
    raw_logs = get_raw_data_for_fitting(config)
    full_dataset = PretrainDataset(config, encoder, raw_logs)

    # --- 【修改】将数据集划分为 80% 训练, 10% 验证, 10% 测试 ---
    train_size = int(0.8 * len(full_dataset))
    val_size = int(0.1 * len(full_dataset))
    test_size = len(full_dataset) - train_size - val_size
    train_dataset, val_dataset, test_dataset = random_split(full_dataset, [train_size, val_size, test_size])

    train_dataloader = DataLoader(train_dataset, batch_size=config.batch_size, shuffle=True, collate_fn=PretrainDataset.collate_fn)
    val_dataloader = DataLoader(val_dataset, batch_size=config.batch_size, shuffle=False, collate_fn=PretrainDataset.collate_fn)
    test_dataloader = DataLoader(test_dataset, batch_size=config.batch_size, shuffle=False, collate_fn=PretrainDataset.collate_fn) # 新增测试数据加载器
    
    logging.info(
        f"Datasets ready. Train: {len(train_dataset)}, Validation: {len(val_dataset)}, Test: {len(test_dataset)}"
    )

    # --- 3. 初始化模型、损失函数和优化器 ---
    # model = LogMamba(config).to(config.device)
    model = BiDirectionalLogMamba(config).to(config.device)
    
    mlm_criterion = nn.CrossEntropyLoss(ignore_index=-100) 
    rpd_criterion = nn.BCEWithLogitsLoss()
    eco_criterion = nn.BCEWithLogitsLoss()

    optimizer = AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)

    # --- 4. 训练循环 ---
    logging.info("Starting pre-training...")
    best_val_loss = float('inf')

    for epoch in range(config.epochs):
        # ==================== 训练阶段 ====================
        model.train()
        
        total_train_loss = 0
        total_train_mlm_correct, total_train_mlm_count = 0, 0
        total_train_rpd_correct, total_train_rpd_count = 0, 0
        total_train_eco_correct, total_train_eco_count = 0, 0
        
        train_loop = tqdm(train_dataloader, desc=f"Epoch {epoch+1}/{config.epochs} [Train]")
        
        for batch in train_loop:
            template_ids = batch['template_ids'].to(config.device)
            param_ids = batch['param_ids'].to(config.device)
            mlm_labels = batch['mlm_labels'].to(config.device)
            rpd_labels = batch['rpd_labels'].to(config.device)
            eco_labels = batch['eco_labels'].to(config.device)

            mlm_logits, rpd_logits, eco_logits = model(template_ids, param_ids)

            loss_mlm = mlm_criterion(mlm_logits.view(-1, config.template_vocab_size), mlm_labels.view(-1))
            loss_rpd = rpd_criterion(rpd_logits.view(-1), rpd_labels.view(-1))
            loss_eco = eco_criterion(eco_logits.view(-1), eco_labels.view(-1))

            total_loss = (config.mlm_weight * loss_mlm + 
                          config.rpd_weight * loss_rpd + 
                          config.eco_weight * loss_eco)
            
            optimizer.zero_grad()
            total_loss.backward()
            optimizer.step()

            total_train_loss += total_loss.item()

            # 计算训练准确率
            with torch.no_grad():
                mlm_mask = mlm_labels != -100
                if mlm_mask.sum() > 0:
                    mlm_preds = torch.argmax(mlm_logits, dim=-1)
                    total_train_mlm_correct += (mlm_preds[mlm_mask] == mlm_labels[mlm_mask]).sum().item()
                    total_train_mlm_count += mlm_mask.sum().item()
                
                rpd_preds = (rpd_logits > 0).float()
                total_train_rpd_correct += (rpd_preds == rpd_labels).sum().item()
                total_train_rpd_count += rpd_labels.numel()

                eco_preds = (eco_logits > 0).float()
                total_train_eco_correct += (eco_preds == eco_labels).sum().item()
                total_train_eco_count += eco_labels.numel()

            # 更新 tqdm 进度条
            train_mlm_acc = total_train_mlm_correct / total_train_mlm_count if total_train_mlm_count > 0 else 0
            train_rpd_acc = total_train_rpd_correct / total_train_rpd_count if total_train_rpd_count > 0 else 0
            train_eco_acc = total_train_eco_correct / total_train_eco_count if total_train_eco_count > 0 else 0
            train_loop.set_postfix(
                loss=total_loss.item(), 
                mlm_acc=f"{train_mlm_acc:.4f}",
                rpd_acc=f"{train_rpd_acc:.4f}",
                eco_acc=f"{train_eco_acc:.4f}"
            )

        avg_train_loss = total_train_loss / len(train_dataloader)
        avg_train_mlm_acc = total_train_mlm_correct / total_train_mlm_count if total_train_mlm_count > 0 else 0
        avg_train_rpd_acc = total_train_rpd_correct / total_train_rpd_count if total_train_rpd_count > 0 else 0
        avg_train_eco_acc = total_train_eco_correct / total_train_eco_count if total_train_eco_count > 0 else 0
        
        swanlab.log({
            "Loss/train": avg_train_loss, 
            "Accuracy/train_mlm": avg_train_mlm_acc,
            "Accuracy/train_rpd": avg_train_rpd_acc,
            "Accuracy/train_eco": avg_train_eco_acc,
            "Epoch": epoch + 1
        })

        # ==================== 验证阶段 ====================
        # --- 【修改】调用重构的评估函数 ---
        val_metrics = evaluate_model(
            model, val_dataloader, mlm_criterion, rpd_criterion, eco_criterion, 
            config, config.device, description=f"Epoch {epoch+1}/{config.epochs} [Val]"
        )
        avg_val_loss = val_metrics["loss"]
        avg_val_mlm_acc = val_metrics["mlm_acc"]
        avg_val_rpd_acc = val_metrics["rpd_acc"]
        avg_val_eco_acc = val_metrics["eco_acc"]

        logging.info(
            f"Epoch {epoch+1} Summary - "
            f"Train Loss: {avg_train_loss:.4f}, Train MLM Acc: {avg_train_mlm_acc:.4f}, Train RPD Acc: {avg_train_rpd_acc:.4f}, Train ECO Acc: {avg_train_eco_acc:.4f} | "
            f"Val Loss: {avg_val_loss:.4f}, Val MLM Acc: {avg_val_mlm_acc:.4f}, Val RPD Acc: {avg_val_rpd_acc:.4f}, Val ECO Acc: {avg_val_eco_acc:.4f}"
        )
        
        swanlab.log({
            "Loss/validation": avg_val_loss,
            "Accuracy/val_mlm": avg_val_mlm_acc,
            "Accuracy/val_rpd": avg_val_rpd_acc,
            "Accuracy/val_eco": avg_val_eco_acc,
            "Epoch": epoch + 1
        })

        # 保存最佳模型
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save(model.state_dict(), config.mamba_model_save_path)
            logging.info(f"🎉 New best model saved with Val Loss: {best_val_loss:.4f} at '{config.mamba_model_save_path}'")

    logging.info("Pre-training finished.")
    
    # --- 5. 【新增】最终测试阶段 ---
    logging.info("="*50)
    logging.info("       Running Final Evaluation on the Test Set       ")
    logging.info("="*50)
    
    # 加载在验证集上表现最好的模型
    logging.info(f"Loading best model from '{config.mamba_model_save_path}' for final testing...")
    # model = LogMamba(config).to(config.device)
    model = BiDirectionalLogMamba(config).to(config.device)
    model.load_state_dict(torch.load(config.mamba_model_save_path, map_location=config.device))
    
    # 在测试集上评估模型
    test_metrics = evaluate_model(
        model, test_dataloader, mlm_criterion, rpd_criterion, eco_criterion,
        config, config.device, description="Final Test"
    )

    # 打印最终测试结果
    logging.info("--- Final Test Results ---")
    logging.info(f"  - Test Loss: {test_metrics['loss']:.4f}")
    logging.info(f"  - Test MLM Accuracy: {test_metrics['mlm_acc']:.4f}")
    logging.info(f"  - Test RPD Accuracy: {test_metrics['rpd_acc']:.4f}")
    logging.info(f"  - Test ECO Accuracy: {test_metrics['eco_acc']:.4f}")
    logging.info("="*50)
    
    # 也可以将最终测试结果记录到 swanlab
    swanlab.log({
        "Test/loss": test_metrics['loss'],
        "Test/mlm_accuracy": test_metrics['mlm_acc'],
        "Test/rpd_accuracy": test_metrics['rpd_acc'],
        "Test/eco_accuracy": test_metrics['eco_acc'],
    })

    swanlab.finish()


if __name__ == "__main__":    
    config = Config()
    pretrain_model(config)