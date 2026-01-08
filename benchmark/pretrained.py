import os
import torch
import random
import numpy as np
import logging
from typing import List, Dict
from tqdm import tqdm
from sklearn.cluster import KMeans
from torch.utils.data import DataLoader, Dataset
from torch.optim import AdamW

from transformers import BertTokenizer, BertForNextSentencePrediction

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LogNSPDataset(Dataset):
 """
 Helper class to create NSP (Next Sentence Prediction) pairs for PyTorch DataLoader.
 """
 def __init__(self, tokenizer, logs: List[Dict], max_length: int = 512):
 self.tokenizer = tokenizer
 self.max_length = max_length
 self.samples = []
 
 # 1. Sort logs by timestamp to ensure temporal continuity
 # Assuming 'Timestamp' exists, otherwise rely on list order
 sorted_logs = sorted(logs, key=lambda x: x.get('Timestamp', 0))
 texts = [log.get('LogContent', '') for log in sorted_logs]
 
 num_logs = len(texts)
 if num_logs < 2:
 return

 # 2. Generate Pairs
 # We generate 50% IsNext (Positive) and 50% NotNext (Negative)
 for i in range(num_logs - 1):
 # --- Positive Sample (IsNext) ---
 text_a = texts[i]
 text_b = texts[i+1]
 # Label 0 = IsNext (in HuggingFace BERT)
 self.samples.append((text_a, text_b, 0))
 
 # --- Negative Sample (NotNext) ---
 # Pick a random log that is NOT the immediate next one
 rand_idx = random.randint(0, num_logs - 1)
 while rand_idx == i + 1: # Retry if we accidentally picked the real next one
 rand_idx = random.randint(0, num_logs - 1)
 
 text_b_rand = texts[rand_idx]
 # Label 1 = NotNext
 self.samples.append((text_a, text_b_rand, 1))

 def __len__(self):
 return len(self.samples)

 def __getitem__(self, idx):
 text_a, text_b, label = self.samples[idx]
 
 # Tokenize the pair
 encoding = self.tokenizer(
 text_a, 
 text_b,
 truncation=True,
 max_length=self.max_length,
 padding='max_length', # Pad to constant length for batching
 return_tensors='pt'
 )
 
 return {
 'input_ids': encoding['input_ids'].squeeze(0),
 'attention_mask': encoding['attention_mask'].squeeze(0),
 'token_type_ids': encoding['token_type_ids'].squeeze(0),
 'labels': torch.tensor(label, dtype=torch.long)
 }

class PretrainedBaseline:
 """
 Baseline 3: Pre-trained Language Model (BERT NSP Fine-tuning + K-Means)
 1. Fine-tunes BERT on the Next Sentence Prediction (NSP) task using log data.
 2. Extracts embeddings using the fine-tuned model.
 3. Clusters embeddings using K-Means.
 """
 def __init__(self, 
 base_model_path: str = './benchmark/bert-base-uncased/', 
 model_save_dir: str = './saved_models/bert_nsp_finetuned/', # New: save path
 n_clusters: int = 10, 
 batch_size: int = 16, 
 device: str = 'cuda', 
 epochs: int = 5, 
 lr: float = 5e-5,
 patience: int = 2): # New: early stopping patience
 
 if BertForNextSentencePrediction is None:
 raise ImportError("Transformers library not installed. Please install via `pip install transformers`.")
 
 self.base_model_path = base_model_path
 self.model_save_dir = model_save_dir
 self.n_clusters = n_clusters
 self.batch_size = batch_size
 self.epochs = epochs
 self.lr = lr
 self.patience = patience
 self.device = device if torch.cuda.is_available() else 'cpu'
 
 self.tokenizer = None
 self.model = None
 self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
 self.is_fitted = False
 self.needs_training = True # Mark whether training is needed

 self._load_model()

 def _load_model(self):
 """
 Loads BERT. 
 Priority:
 1. Load from model_save_dir (if exists) -> Skip training
 2. Load from base_model_path -> Needs training
 """
 # Check if trained model exists
 if os.path.exists(self.model_save_dir) and os.listdir(self.model_save_dir):
 logger.info(f"Pretrained: Found saved model in {self.model_save_dir}. Loading...")
 try:
 self.tokenizer = BertTokenizer.from_pretrained(self.model_save_dir)
 self.model = BertForNextSentencePrediction.from_pretrained(self.model_save_dir)
 self.model.to(self.device)
 self.needs_training = False # Mark as not needing training
 logger.info("Pretrained: Successfully loaded fine-tuned model from disk.")
 return
 except Exception as e:
 logger.warning(f"Pretrained: Failed to load saved model ({e}). Falling back to base model.")
 
 # If no saved model exists or loading fails, load base model
 if not os.path.exists(self.base_model_path):
 # If local path doesn't exist, try downloading from HuggingFace Hub (if network access is allowed)
 logger.warning(f"Local base path {self.base_model_path} not found. Trying 'bert-base-uncased' from Hub.")
 base_path = 'bert-base-uncased'
 else:
 base_path = self.base_model_path

 logger.info(f"Pretrained: Loading base BERT from {base_path}...")
 try:
 self.tokenizer = BertTokenizer.from_pretrained(base_path)
 self.model = BertForNextSentencePrediction.from_pretrained(base_path)
 self.model.to(self.device)
 self.needs_training = True # Mark as needing training
 except Exception as e:
 logger.error(f"Pretrained: Failed to load base BERT model: {e}")
 raise e

 def _train_nsp(self, logs: List[Dict]):
 """
 Fine-tunes the BERT model on the Next Sentence Prediction task with Early Stopping.
 """
 logger.info("Pretrained: Preparing NSP dataset...")
 dataset = LogNSPDataset(self.tokenizer, logs)
 
 if len(dataset) == 0:
 logger.warning("Not enough logs to create NSP pairs.")
 return

 dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
 optimizer = AdamW(self.model.parameters(), lr=self.lr)

 self.model.train()
 logger.info(f"Pretrained: Starting NSP Fine-tuning for {self.epochs} epochs on {len(dataset)} samples...")

 # Early stopping related variables
 best_loss = float('inf')
 patience_counter = 0
 min_delta = 0.001 # loss must decrease by at least this much to be considered improvement

 for epoch in range(self.epochs):
 total_loss = 0
 progress_bar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{self.epochs} [NSP Train]")
 
 for batch in progress_bar:
 input_ids = batch['input_ids'].to(self.device)
 attention_mask = batch['attention_mask'].to(self.device)
 token_type_ids = batch['token_type_ids'].to(self.device)
 labels = batch['labels'].to(self.device)

 outputs = self.model(
 input_ids=input_ids,
 attention_mask=attention_mask,
 token_type_ids=token_type_ids,
 labels=labels
 )
 
 loss = outputs.loss
 total_loss += loss.item()

 optimizer.zero_grad()
 loss.backward()
 optimizer.step()
 
 progress_bar.set_postfix({'loss': f"{loss.item():.4f}"})
 
 avg_loss = total_loss / len(dataloader)
 logger.info(f"Epoch {epoch+1} completed. Average Loss: {avg_loss:.4f}")

 # --- Early Stopping Check ---
 if avg_loss < (best_loss - min_delta):
 best_loss = avg_loss
 patience_counter = 0
 # Optional: save best checkpoint here, currently we only save at the end
 else:
 patience_counter += 1
 logger.info(f"Early Stopping Counter: {patience_counter}/{self.patience}")
 if patience_counter >= self.patience:
 logger.info("🛑 Early stopping triggered.")
 break
 
 # --- Training complete, save model ---
 logger.info(f"Pretrained: Saving fine-tuned model to {self.model_save_dir}...")
 if not os.path.exists(self.model_save_dir):
 os.makedirs(self.model_save_dir)
 
 self.model.save_pretrained(self.model_save_dir)
 self.tokenizer.save_pretrained(self.model_save_dir)
 logger.info("Pretrained: Model saved successfully.")

 def _get_embeddings(self, logs: List[Dict]) -> np.ndarray:
 """
 Generates BERT embeddings using the (potentially fine-tuned) model.
 """
 self.model.eval() # Ensure eval mode
 all_embeddings = []
 texts = [log.get('LogContent', '') for log in logs]
 
 total_batches = (len(texts) + self.batch_size - 1) // self.batch_size
 
 with torch.no_grad():
 for i in tqdm(range(0, len(texts), self.batch_size), desc="Extracting Embeddings", total=total_batches):
 batch_texts = texts[i : i + self.batch_size]
 
 encoded_input = self.tokenizer(
 batch_texts,
 padding=True,
 truncation=True,
 max_length=128,
 return_tensors='pt'
 )
 
 input_ids = encoded_input['input_ids'].to(self.device)
 attention_mask = encoded_input['attention_mask'].to(self.device)
 
 # BertForNextSentencePrediction -> self.model.bert
 base_model = self.model.bert 
 outputs = base_model(input_ids=input_ids, attention_mask=attention_mask)
 
 # Extract [CLS] token embedding (batch_size, hidden_dim)
 cls_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
 all_embeddings.append(cls_embeddings)
 
 if not all_embeddings:
 return np.empty((0, 768))
 
 return np.vstack(all_embeddings)

 def fit(self, logs: List[Dict]):
 """
 Phase 1: Fine-tune BERT on NSP task (ONLY if model was not loaded from disk).
 Phase 2: Extract embeddings from the fine-tuned model and train K-Means.
 """
 # 1. Fine-tune BERT (NSP)
 if self.needs_training:
 logger.info("Pretrained: Model needs training. Starting fine-tuning...")
 self._train_nsp(logs)
 else:
 logger.info("Pretrained: Model loaded from disk. Skipping fine-tuning.")
 
 # 2. Extract Embeddings & Fit K-Means
 logger.info("Pretrained: Extracting embeddings for K-Means training...")
 X = self._get_embeddings(logs)
 
 logger.info(f"Pretrained: Fitting K-Means (k={self.n_clusters})...")
 self.kmeans.fit(X)
 self.is_fitted = True
 logger.info("Pretrained: Fit complete.")

 def predict(self, logs: List[Dict]) -> List[List[int]]:
 """
 Extracts embeddings (using fine-tuned BERT) and predicts clusters.
 """
 if not logs:
 return []
 
 X = self._get_embeddings(logs)
 
 if not self.is_fitted:
 logger.warning("Pretrained: Model not fitted! Running fit_predict (Transductive).")
 labels = self.kmeans.fit_predict(X)
 else:
 labels = self.kmeans.predict(X)

 # Group by cluster ID
 clusters = {}
 for idx, label in enumerate(labels):
 if label not in clusters:
 clusters[label] = []
 clusters[label].append(idx)
 
 sessions = list(clusters.values())
 # Sort sessions by timestamp of the first log in the session
 sessions.sort(key=lambda s: logs[s[0]].get('Timestamp', 0) if s else 0)
 
 return sessions

