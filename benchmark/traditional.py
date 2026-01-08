# benchmark/traditional.py

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from typing import List, Dict
import logging

class TraditionalBaseline:
 """
 Baseline 1: Traditional Method (Drain + TF-IDF + K-Means)
 Updated to support fit (on train) and predict (on test).
 """
 def __init__(self, n_clusters: int = 10):
 self.n_clusters = n_clusters
 self.vectorizer = TfidfVectorizer(
 analyzer='word',
 stop_words='english',
 max_features=1000
 )
 self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
 self.is_fitted = False

 def fit(self, logs: List[Dict]):
 """
 Train TF-IDF and K-Means on training logs.
 """
 logging.info("Traditional: Fitting TF-IDF and K-Means on training data...")
 if not logs:
 logging.warning("Traditional: Empty training logs.")
 return

 # Extract templates
 corpus = [log.get('LogContent', '') for log in logs]
 
 # Fit TF-IDF
 X = self.vectorizer.fit_transform(corpus)
 
 # Fit K-Means
 self.kmeans.fit(X)
 self.is_fitted = True
 logging.info("Traditional: Fitting complete.")

 def predict(self, logs: List[Dict]) -> List[List[int]]:
 """
 Predict clusters for test logs and group them into sessions.
 """
 logging.info("Traditional: Predicting on test data...")
 if not logs:
 return []
 
 if not self.is_fitted:
 logging.warning("Traditional: Model not fitted! Running fit_predict on test data as fallback.")
 # Fallback for transductive usage if fit wasn't called
 corpus = [log.get('EventTemplate', '') for log in logs]
 X = self.vectorizer.fit_transform(corpus)
 labels = self.kmeans.fit_predict(X)
 else:
 # Standard inductive usage
 corpus = [log.get('EventTemplate', '') for log in logs]
 X = self.vectorizer.transform(corpus)
 labels = self.kmeans.predict(X)

 # Group indices by cluster label to form "sessions" (Event Type Clusters)
 # Note: As discussed, K-Means groups by content type. 
 # To make it a valid sessionizer, we usually sort by time.
 clusters = {}
 for idx, label in enumerate(labels):
 if label not in clusters:
 clusters[label] = []
 clusters[label].append(idx)
 
 sessions = list(clusters.values())
 
 # Sort sessions by timestamp of the first log
 sessions.sort(key=lambda s: logs[s[0]]['Timestamp'] if s else 0)
 
 return sessions
 

