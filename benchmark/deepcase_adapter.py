# benchmark/deepcase_adapter.py

import logging
import torch
import numpy as np
from typing import List, Dict, Tuple, Any
from datetime import timedelta

from deepcase.context_builder import ContextBuilder
from deepcase.interpreter import Interpreter

class DeepCaseAdapter:
 """
 Adapter for DeepCASE SOTA method.
 Wraps the official DeepCASE logic (ContextBuilder + Interpreter) to work with
 our in-memory log data structure.
 """
 def __init__(self, template_map: Dict[str, int], timeout: int = 300, device: str = 'cuda'):
 if ContextBuilder is None:
 raise ImportError("DeepCASE library is not installed. Please install it via pip.")
 
 self.template_map = template_map
 self.timeout = timedelta(seconds=timeout)
 self.device = device if torch.cuda.is_available() else 'cpu'
 
 # DeepCASE Hyperparameters (Aligned with their paper/example)
 self.context_length = 10
 self.hidden_size = 128
 self.input_size = len(template_map) + 1 # +1 for unknown/padding
 
 self.context_builder = None
 self.interpreter = None
 self.train_clusters = None

 def _preprocess_sessionize(self, logs: List[Dict]) -> List[List[int]]:
 """
 Mimics DeepCASE Preprocessor: Splits logs into sessions based on Time Timeout.
 Returns a list of sessions (each session is a list of log indices).
 """
 if not logs:
 return []
 
 # Ensure logs are sorted by timestamp
 # Note: We assume logs passed here are already sorted or we sort them locally
 # Using indices to track original positions
 indexed_logs = sorted(enumerate(logs), key=lambda x: x[1]['Timestamp'])
 
 sessions = []
 current_session = []
 
 if indexed_logs:
 current_session.append(indexed_logs[0][0])
 
 for i in range(1, len(indexed_logs)):
 curr_idx, curr_log = indexed_logs[i]
 prev_idx, prev_log = indexed_logs[i-1]
 
 time_diff = curr_log['Timestamp'] - prev_log['Timestamp']
 
 if time_diff > self.timeout:
 sessions.append(current_session)
 current_session = []
 
 current_session.append(curr_idx)
 
 if current_session:
 sessions.append(current_session)
 
 return sessions

 def _create_sequences(self, sessions: List[List[int]], logs: List[Dict]) -> Tuple[torch.Tensor, torch.Tensor]:
 """
 Converts sessions into (Context, Event) pairs for DeepCASE training.
 X shape: (N, context_length)
 y shape: (N, 1)
 """
 X_list = []
 y_list = []
 
 for session in sessions:
 # Convert log indices to Template IDs
 seq_ids = []
 for idx in session:
 template = logs[idx].get('EventTemplate', '')
 # Map to ID, default to 0 if unknown
 tid = self.template_map.get(template, 0)
 seq_ids.append(tid)
 
 # Generate sliding windows
 # DeepCASE logic: Context of length L predicts next event
 for i in range(len(seq_ids)):
 # Target
 target = seq_ids[i]
 
 # Context (padding with -1 or 0 if strictly following their logic, 
 # but usually embedding layers handle 0 as padding)
 if i < self.context_length:
 # Pad with 0
 ctx = [0] * (self.context_length - i) + seq_ids[:i]
 else:
 ctx = seq_ids[i - self.context_length : i]
 
 X_list.append(ctx)
 y_list.append([target])
 
 if not X_list:
 return torch.empty(0), torch.empty(0)

 X = torch.tensor(X_list, dtype=torch.long)
 y = torch.tensor(y_list, dtype=torch.long)
 return X, y

 def fit(self, train_logs: List[Dict]):
 """
 1. Sessionize Train Logs.
 2. Train ContextBuilder (LSTM/Attention).
 3. Cluster using Interpreter.
 """
 logging.info("DeepCASE: Sessionizing training data...")
 self.train_sessions = self._preprocess_sessionize(train_logs)
 
 logging.info("DeepCASE: Creating sequences for training...")
 X_train, y_train = self._create_sequences(self.train_sessions, train_logs)
 
 if self.device == 'cuda':
 X_train = X_train.to('cuda')
 y_train = y_train.to('cuda')

 # --- 1. Train ContextBuilder ---
 logging.info("DeepCASE: Training ContextBuilder...")
 # Note: input_size in DeepCASE usually refers to One-Hot size or Embedding vocab size.
 # If using embeddings, we need to ensure ContextBuilder supports it.
 # The official example uses `input_size` as feature dim. 
 # Assuming standard DeepCASE usage where input is mapped to embeddings internally or one-hot.
 # For simplicity, we assume input_size = vocab_size.
 
 self.context_builder = ContextBuilder(
 input_size = self.input_size,
 output_size = self.input_size,
 hidden_size = self.hidden_size,
 max_length = self.context_length,
 )
 
 if self.device == 'cuda':
 self.context_builder = self.context_builder.to('cuda')

 self.context_builder.fit(
 X = X_train,
 y = y_train,
 epochs = 5, # Reduced for benchmark speed, increase for paper
 batch_size = 128,
 learning_rate = 0.01,
 verbose = True,
 )

 # --- 2. Cluster with Interpreter ---
 logging.info("DeepCASE: Clustering training patterns with Interpreter...")
 self.interpreter = Interpreter(
 context_builder = self.context_builder,
 features = self.input_size,
 eps = 0.1,
 min_samples = 5,
 threshold = 0.2,
 )
 
 self.train_clusters = self.interpreter.cluster(
 X = X_train,
 y = y_train,
 iterations = 50, # Reduced for speed
 batch_size = 1024,
 verbose = True,
 )
 
 # Assign dummy scores (Normal=-1) just to finalize the state
 # In a real anomaly detection scenario, we would label these.
 # Here we just want the clustering structure.
 dummy_labels = np.full(y_train.shape[0], 0, dtype=int) 
 
 # Check if any clusters were actually found (DeepCASE might return only noise -1)
 unique_clusters = np.unique(self.train_clusters)
 if len(unique_clusters) == 0 or (len(unique_clusters) == 1 and unique_clusters[0] == -1):
 logging.warning("DeepCASE: No valid clusters found (all noise). Skipping scoring.")
 else:
 try:
 scores = self.interpreter.score_clusters(scores=dummy_labels, strategy="max", NO_SCORE=-1)
 self.interpreter.score(scores=scores, verbose=False)
 except ValueError as e:
 logging.warning(f"DeepCASE: Scoring failed despite fix (likely no samples in specific clusters): {e}")
 
 logging.info("DeepCASE: Training and Clustering Complete.")

 def predict(self, test_logs: List[Dict]) -> Tuple[List[List[int]], np.ndarray]:
 """
 1. Sessionize Test Logs (This is the partitioning result).
 2. Predict clusters for test sequences (This is the classification result).
 
 Returns:
 sessions: List[List[int]] - The session partition.
 predictions: np.ndarray - The cluster ID for each sequence step.
 """
 logging.info("DeepCASE: Sessionizing test data...")
 # 1. Partitioning Result
 test_sessions = self._preprocess_sessionize(test_logs)
 
 logging.info("DeepCASE: Predicting on test sequences...")
 X_test, y_test = self._create_sequences(test_sessions, test_logs)
 
 if self.device == 'cuda':
 X_test = X_test.to('cuda')
 y_test = y_test.to('cuda')

 # 2. Classification Result (Semi-Automatic Mode)
 # prediction contains the scores/cluster-ids
 prediction = self.interpreter.predict(
 X = X_test,
 y = y_test,
 iterations = 50,
 batch_size = 1024,
 verbose = True,
 )
 
 return test_sessions, prediction

