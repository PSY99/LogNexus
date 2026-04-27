# knowledge_base/knowledge_base_builder.py

import os
import json
import logging
import random
from collections import defaultdict
from typing import List, Dict, Any, Optional

import torch
import numpy as np
import faiss
from tqdm import tqdm

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from utils.llm_utils import call_llm_api, initialize_llm_client
from data_preprocessing.unified_encoder import UnifiedLogEncoder
from data_preprocessing.dataset import BaseDataset
from event_refinement.model.bi_directional_log_mamba import BiDirectionalLogMamba

PROMPT_FOR_EVENT_GENERALIZATION = """
You are a senior cybersecurity and operations analyst. Your task is to analyze a set of log samples representing a single type of event and create a generalized knowledge entry.

### Log Samples:
{log_samples_string}

### Your Tasks:
1.  **Generalized Summary**: Write a concise, one-sentence, generalized summary of what this event type represents. This summary MUST NOT contain any specific values from the logs (e.g., instead of "user 'admin' failed to log in", write "A user failed to log in."). Use placeholders like [User], [IP], [FileName] if needed.
2.  **Key Parameters**: Identify the semantic roles of the variable parts in the logs (e.g., "user", "source_ip", "port", "error_code").
3.  **Suggested Action**: Provide a brief, actionable suggestion for what a human analyst should do when seeing this event (e.g., "Monitor for further attempts from this IP.", "No action needed, informational.", "Investigate user account for compromise.").
4.  **Severity**: Classify the event's severity. Choose ONE from: "Informational", "Warning", "Error", "Critical".

### Output Format:
Your output MUST be a single, valid JSON object with four keys: "generalized_summary", "key_parameters", "suggested_action", and "severity".

Example:
{{
    "generalized_summary": "A user successfully authenticated and started a new session.",
    "key_parameters": ["user", "source_ip", "port"],
    "suggested_action": "No action needed, this is a normal operational log. Correlate with other logs from the same session for context.",
    "severity": "Informational"
}}

Provide ONLY the JSON object.
"""


class KnowledgeBaseBuilder:
    """
    Builds and maintains a Security Knowledge Base (SKB) from refined events.
    The SKB is built incrementally and uses semantic search to group similar events,
    reducing redundancy and LLM calls. This version includes verification and annotation features.
    The event types are dynamic and evolve as new refined events are assigned.
    """

    def __init__(self, config: Config, model: BiDirectionalLogMamba, encoder: UnifiedLogEncoder, llm_client: Any):
        self.config = config
        self.model = model
        self.encoder = encoder
        self.llm_client = llm_client
        self.model.eval().to(config.device)
        
        self.kb_dir = config.kb_dir
        self.verification_dir = os.path.join(self.kb_dir, "verification")
        os.makedirs(self.kb_dir, exist_ok=True)
        os.makedirs(self.verification_dir, exist_ok=True)
        
        self.similarity_threshold = config.kb_cosine_similarity_threshold
        self.llm_update_threshold = config.kb_llm_update_threshold

        self.knowledge_base = []
        self.faiss_index = None
        # --- NEW 1: 初始化一个内存中的向量缓存 ---
        self.event_embeddings = {}
        
        self._load_existing_kb()
        
        logging.info(f"KnowledgeBaseBuilder initialized. Loaded {len(self.knowledge_base)} existing event entries.")

    def _load_existing_kb(self):
        """Loads the knowledge base and populates the in-memory embedding cache."""
        kb_json_path = os.path.join(self.kb_dir, "knowledge_base.json")
        kb_faiss_path = os.path.join(self.kb_dir, "kb_embeddings.faiss")
        if os.path.exists(kb_json_path) and os.path.exists(kb_faiss_path):
            try:
                with open(kb_json_path, 'r', encoding='utf-8') as f:
                    self.knowledge_base = json.load(f)
                
                self.faiss_index = faiss.read_index(kb_faiss_path)
                
                # --- NEW 2: 从FAISS索引重建内存中的向量缓存 ---
                if isinstance(self.faiss_index, faiss.IndexIDMap) and self.faiss_index.ntotal > 0:
                    # 获取存储在IndexIDMap中的所有自定义ID
                    list_of_ids = faiss.vector_to_array(self.faiss_index.id_map)
                    # 获取IndexIDMap包装的底层索引 (e.g., IndexFlatIP)
                    sub_index = self.faiss_index.index
                    # 遍历所有向量，通过它们的内部顺序ID (0, 1, 2...) 来重建
                    for i, custom_id in enumerate(list_of_ids):
                        # 从底层索引重建向量
                        vector = sub_index.reconstruct(i)
                        # 存入我们的缓存
                        self.event_embeddings[int(custom_id)] = vector
                    logging.info(f"Successfully rebuilt in-memory embedding cache with {len(self.event_embeddings)} vectors.")
                
                logging.info(f"Successfully loaded existing knowledge base with {self.faiss_index.ntotal} entries.")
            except Exception as e:
                logging.warning(f"Could not load existing knowledge base, will start from scratch. Error: {e}")
                self.knowledge_base = []
                self.faiss_index = None
                self.event_embeddings = {}

    def _get_representative_embedding(self, session_indices: List[int], raw_logs: List[Dict], include_params: bool = False) -> np.ndarray:
        """
        Calculates the mean embedding of logs for the provided indices. Can include or exclude parameters.
        For KB building, we set `include_params=False` to get a general semantic embedding.
        It also samples logs if the session is too large.
        """
        if not session_indices:
            return np.zeros(self.model.config.mamba_d_model * 2)

        if len(session_indices) > self.config.kb_embedding_sample_size:
            indices_to_embed = random.sample(session_indices, self.config.kb_embedding_sample_size)
        else:
            indices_to_embed = session_indices

        embeddings = []
        BATCH_SIZE = 32

        with torch.no_grad():
            for i in range(0, len(indices_to_embed), BATCH_SIZE):
                batch_indices = indices_to_embed[i:i + BATCH_SIZE]
                batch_template_ids = []
                batch_param_ids_list = []

                for log_idx in batch_indices:
                    log = raw_logs[log_idx]
                    encoded = self.encoder.encode(log, include_params=include_params)
                    batch_template_ids.append(encoded['template_id'])
                    batch_param_ids_list.append(encoded['param_ids'])

                if not batch_template_ids:
                    continue

                template_tensor = torch.tensor([[tid] for tid in batch_template_ids], dtype=torch.long).to(self.config.device)
                param_tensor = torch.stack(batch_param_ids_list, dim=0).to(self.config.device)

                mamba_out, _, _ = self.model(template_tensor, param_tensor)
                log_embeddings_batch = mamba_out.squeeze(1).cpu().numpy()
                embeddings.extend(log_embeddings_batch)
        
        if not embeddings:
            return np.zeros(self.model.config.mamba_d_model * 2)
            
        mean_embedding = np.mean(embeddings, axis=0).astype('float32')
        
        faiss.normalize_L2(mean_embedding.reshape(1, -1))
        return mean_embedding

    def _get_event_generalization(self, session_indices: List[int], raw_logs: List[Dict], event_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Uses LLM to generate or update a GENERALIZED summary.
        If event_id is provided, it samples from the historical verification logs for a richer context.
        """
        log_samples = []
        if event_id is not None:
            verification_path = os.path.join(self.verification_dir, f"event_{event_id}_logs.json")
            if os.path.exists(verification_path):
                try:
                    with open(verification_path, 'r', encoding='utf-8') as f:
                        all_sessions_data = json.load(f)
                    all_logs = [log for session in all_sessions_data for log in session['log_contents']]
                    sample_size = min(len(all_logs), 15)
                    log_samples = random.sample(all_logs, sample_size)
                except (json.JSONDecodeError, IndexError):
                     logging.warning(f"Could not sample from verification file for event {event_id}. Using current session logs.")
                     log_samples = []
        
        if not log_samples:
            unique_template_logs = {raw_logs[i]['EventTemplate']: raw_logs[i]['LogContent'] for i in session_indices}
            log_samples = list(unique_template_logs.values())[:15]

        log_samples_str = "\n".join(log_samples)

        prompt = PROMPT_FOR_EVENT_GENERALIZATION.format(log_samples_string=log_samples_str)
        
        try:
            response_str = call_llm_api(self.llm_client, prompt, self.config.llm_model_name, self.config)
            summary_data = json.loads(response_str)
            if all(k in summary_data for k in ["generalized_summary", "key_parameters", "suggested_action", "severity"]):
                return summary_data
        except Exception as e:
            logging.error(f"Failed to get generalization for an event: {e}. Falling back.")
        
        return {
            "generalized_summary": "Summary generation failed.",
            "key_parameters": [],
            "suggested_action": "Manual investigation required due to generation failure.",
            "severity": "Unknown"
        }

    def _find_semantically_similar_event(self, embedding: np.ndarray) -> Optional[int]:
        """
        Searches the FAISS index for a semantically similar event using Cosine Similarity.
        Returns the event_id of the similar event, or None.
        """
        if self.faiss_index is None or self.faiss_index.ntotal == 0:
            return None

        query_embedding = np.expand_dims(embedding, axis=0)
        
        similarities, ids = self.faiss_index.search(query_embedding, 1)
        
        if ids.size == 0:
            return None

        nearest_similarity = similarities[0][0]
        nearest_event_id = ids[0][0]

        if nearest_similarity > self.similarity_threshold:
            return nearest_event_id
        
        return None

    def _append_to_verification_file(self, event_id: int, session_indices: List[int], raw_logs: List[Dict]):
        """Helper to append session logs to the verification file for an event."""
        verification_path = os.path.join(self.verification_dir, f"event_{event_id}_logs.json")
        
        # --- MODIFICATION START ---
        # 为每个会话添加一个新的标注字段 'session_annotation_correct'，初始值为 null
        session_logs = {
            "session_id": f"session_{random.randint(1000, 9999)}",
            "session_annotation_correct": None, # 新增字段，用于人工标注此会话划分是否正确
            "log_contents": [raw_logs[i]['LogContent'] for i in session_indices]
        }
        # --- MODIFICATION END ---

        try:
            if os.path.exists(verification_path):
                with open(verification_path, 'r+', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
                    data.append(session_logs)
                    f.seek(0)
                    f.truncate()
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                with open(verification_path, 'w', encoding='utf-8') as f:
                    json.dump([session_logs], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to write to verification file {verification_path}: {e}")

    def build(self, refined_events: List[List[int]], raw_logs: List[Dict]):
        """
        Main method to build/update the SKB. Iterates through each refined event, finds or creates
        a corresponding event type based on semantic similarity. Event types evolve over time.
        """
        logging.info(f"Starting Phase III SKB construction from {len(refined_events)} refined events.")
        
        new_events_created = 0
        events_merged = 0

        for refined_event in tqdm(refined_events, desc="Processing Refined Events for SKB"):
            if not refined_event: continue
            
            new_event_embedding = self._get_representative_embedding(refined_event, raw_logs, include_params=False)
            similar_event_id = self._find_semantically_similar_event(new_event_embedding)

            if similar_event_id is not None:
                try:
                    entry_index = next(i for i, entry in enumerate(self.knowledge_base) if entry['event_id'] == similar_event_id)
                    kb_entry = self.knowledge_base[entry_index]
                    
                    # --- MODIFIED 1: 从内存缓存中获取旧向量 ---
                    if similar_event_id not in self.event_embeddings:
                        logging.error(f"FATAL: Event ID {similar_event_id} found in FAISS but not in memory cache. Inconsistency detected. Treating as new event.")
                        similar_event_id = None # 强制创建新事件以避免崩溃
                    else:
                        old_embedding = self.event_embeddings[similar_event_id]
                        instance_count_before_update = kb_entry['instance_count']
                        
                        updated_embedding = (old_embedding * instance_count_before_update + new_event_embedding) / (instance_count_before_update + 1)
                        faiss.normalize_L2(updated_embedding.reshape(1, -1))
                        
                        self.faiss_index.remove_ids(np.array([similar_event_id], dtype=np.int64))
                        self.faiss_index.add_with_ids(updated_embedding.reshape(1, -1), np.array([similar_event_id], dtype=np.int64))

                        # --- NEW 3: 更新内存中的向量缓存 ---
                        self.event_embeddings[similar_event_id] = updated_embedding

                        kb_entry['instance_count'] += 1
                        
                        current_session_templates = {raw_logs[i]['EventTemplate'] for i in refined_event}
                        existing_templates = set(kb_entry['structural_signature'])
                        if not current_session_templates.issubset(existing_templates):
                            kb_entry['structural_signature'] = sorted(list(existing_templates.union(current_session_templates)))
                        
                        if self.llm_update_threshold > 0 and kb_entry['instance_count'] % self.llm_update_threshold == 0:
                            logging.info(f"Event {similar_event_id} reached {kb_entry['instance_count']} instances. Re-running LLM generalization.")
                            generalization_data = self._get_event_generalization(refined_event, raw_logs, event_id=similar_event_id)
                            kb_entry.update(generalization_data)

                        events_merged += 1
                        self._append_to_verification_file(similar_event_id, refined_event, raw_logs)

                except (StopIteration, RuntimeError) as e:
                    logging.warning(f"Error updating event {similar_event_id}: {e}. Treating as a new event.")
                    similar_event_id = None
            
            if similar_event_id is None:
                new_events_created += 1
                
                generalization_data = self._get_event_generalization(refined_event, raw_logs)
                structural_signature = sorted(list({raw_logs[i]['EventTemplate'] for i in refined_event}))
                
                event_id = len(self.knowledge_base) if not self.knowledge_base else max(e['event_id'] for e in self.knowledge_base) + 1

                kb_entry = {
                    "event_id": event_id,
                    "generalized_summary": generalization_data["generalized_summary"],
                    "severity": generalization_data["severity"],
                    "suggested_action": generalization_data["suggested_action"],
                    "key_parameters": generalization_data["key_parameters"],
                    "structural_signature": structural_signature,
                    "instance_count": 1, 
                    "annotation_correct": None
                }
                self.knowledge_base.append(kb_entry)

                embedding_to_add = new_event_embedding.reshape(1, -1)
                if self.faiss_index is None:
                    d = new_event_embedding.shape[0]
                    base_index = faiss.IndexFlatIP(d)
                    self.faiss_index = faiss.IndexIDMap(base_index)
                
                self.faiss_index.add_with_ids(embedding_to_add, np.array([event_id], dtype=np.int64))

                # --- NEW 4: 将新向量添加到内存缓存 ---
                self.event_embeddings[event_id] = new_event_embedding

                self._append_to_verification_file(event_id, refined_event, raw_logs)

        logging.info(f"Phase III summary: {new_events_created} new event types created, {events_merged} refined events assigned to existing event types.")
        self.save_kb()

    def save_kb(self):
        """Saves the knowledge base JSON and FAISS index to disk."""
        if not self.knowledge_base:
            logging.warning("Knowledge base is empty. Nothing to save.")
            return

        kb_json_path = os.path.join(self.kb_dir, "knowledge_base.json")
        with open(kb_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_base, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ Knowledge base signatures saved to {kb_json_path}")

        if self.faiss_index:
            kb_faiss_path = os.path.join(self.kb_dir, "kb_embeddings.faiss")
            faiss.write_index(self.faiss_index, kb_faiss_path)
            logging.info(f"✅ FAISS index with {self.faiss_index.ntotal} vectors saved to {kb_faiss_path}")

        logging.info(f"✅ Verification logs saved in '{self.verification_dir}' directory.")
        logging.info("Knowledge base saving complete.")


if __name__ == '__main__':
    config = Config()
    if not hasattr(config, 'kb_cosine_similarity_threshold'):
        config.kb_cosine_similarity_threshold = 0.95
    if not hasattr(config, 'kb_embedding_sample_size'):
        config.kb_embedding_sample_size = 100
    if not hasattr(config, 'kb_llm_update_threshold'):
        config.kb_llm_update_threshold = 20
        
    llm_client = initialize_llm_client(config)
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("Loading components...")
    encoder: UnifiedLogEncoder = UnifiedLogEncoder.load(config.encoder_save_path)
    config.template_vocab_size = encoder.template_vocab_size
    config.param_vocab_size = encoder.param_vocab_size
    
    model = BiDirectionalLogMamba(config)
    model.load_state_dict(torch.load(config.mamba_model_save_path, map_location=config.device))
    
    evaluation_dataset = BaseDataset(config, encoder, mode='eval', data_source=config.data_source_eval)
    raw_logs = evaluation_dataset.raw_logs
        
    refined_sessions_path = os.path.join(config.artifacts_dir, "refined_sessions.json")
    with open(refined_sessions_path, 'r') as f:
        refined_sessions = json.load(f)

    kb_builder = KnowledgeBaseBuilder(config, model, encoder, llm_client)
    kb_builder.build(refined_sessions, raw_logs)
