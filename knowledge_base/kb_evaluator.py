# knowledge_base/kb_evaluator.py

import os
import json
import logging
import argparse
from typing import List, Dict, Any

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config

class KnowledgeBaseEvaluator:
 """
 Evaluates the accuracy of the event clustering and session grouping in the knowledge base.
 - Event clustering accuracy is based on the 'annotation_correct' field in knowledge_base.json.
 - Session grouping accuracy is based on the 'session_annotation_correct' field in the verification files.
 """

 def __init__(self, kb_dir: str):
 """
 Initializes the evaluator.

 Args:
 kb_dir (str): The directory where the knowledge base is stored.
 """
 self.kb_dir = kb_dir
 self.kb_json_path = os.path.join(kb_dir, "knowledge_base.json")
 self.verification_dir = os.path.join(kb_dir, "verification")
 self.knowledge_base: List[Dict[str, Any]] = []
 
 # Counters for event clustering evaluation
 self.event_correct_count = 0
 self.event_incorrect_count = 0
 self.event_unannotated_count = 0

 # Counters for session grouping evaluation
 self.session_correct_count = 0
 self.session_incorrect_count = 0
 self.session_unannotated_count = 0

 logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

 def _load_kb(self) -> bool:
 """
 Loads the knowledge_base.json file.
 
 Returns:
 bool: True if loading was successful, False otherwise.
 """
 if not os.path.exists(self.kb_json_path):
 logging.error(f"Knowledge base file not found at: {self.kb_json_path}")
 return False
 
 try:
 with open(self.kb_json_path, 'r', encoding='utf-8') as f:
 self.knowledge_base = json.load(f)
 logging.info(f"Successfully loaded knowledge base with {len(self.knowledge_base)} entries.")
 return True
 except json.JSONDecodeError as e:
 logging.error(f"Error decoding JSON from {self.kb_json_path}: {e}")
 return False
 except Exception as e:
 logging.error(f"An unexpected error occurred while loading the KB: {e}")
 return False

 def evaluate_events(self):
 """
 Performs the event clustering evaluation by iterating through the KB entries and
 calculating accuracy based on the 'annotation_correct' field.
 """
 if not self._load_kb():
 return

 if not self.knowledge_base:
 logging.warning("Knowledge base is empty. Nothing to evaluate for events.")
 return

 for entry in self.knowledge_base:
 annotation_value = entry.get("annotation_correct")

 if annotation_value is True:
 self.event_correct_count += 1
 elif annotation_value is False:
 self.event_incorrect_count += 1
 else:
 self.event_unannotated_count += 1
 
 self._print_event_report()

 def evaluate_sessions(self):
 """
 Performs the session grouping evaluation by scanning all verification files
 and checking the 'session_annotation_correct' field.
 """
 if not os.path.isdir(self.verification_dir):
 logging.warning(f"Verification directory not found at: {self.verification_dir}. Cannot evaluate sessions.")
 return
 
 verification_files = [f for f in os.listdir(self.verification_dir) if f.startswith('event_') and f.endswith('_logs.json')]
 
 if not verification_files:
 logging.info("No verification files found to evaluate for sessions.")
 return

 total_files_processed = 0
 for filename in verification_files:
 filepath = os.path.join(self.verification_dir, filename)
 try:
 with open(filepath, 'r', encoding='utf-8') as f:
 sessions_data = json.load(f)
 
 for session_entry in sessions_data:
 annotation_value = session_entry.get("session_annotation_correct")
 
 if annotation_value is True:
 self.session_correct_count += 1
 elif annotation_value is False:
 self.session_incorrect_count += 1
 else:
 self.session_unannotated_count += 1
 total_files_processed += 1
 except Exception as e:
 logging.error(f"Failed to process verification file {filename}: {e}")
 
 logging.info(f"Processed {total_files_processed} verification files for session evaluation.")
 self._print_session_report()

 def _print_event_report(self):
 """Prints a formatted report of the event clustering evaluation results."""
 total_annotated = self.event_correct_count + self.event_incorrect_count
 accuracy = (self.event_correct_count / total_annotated) * 100 if total_annotated > 0 else 0.0
 total_entries = len(self.knowledge_base)

 print("\n" + "="*50)
 print(" KNOWLEDGE BASE EVENT CLUSTERING REPORT")
 print("="*50)
 print(f"Source File: {self.kb_json_path}\n")
 
 print("--- Annotation Statistics ---")
 print(f"Correctly Clustered Events: {self.event_correct_count}")
 print(f"Incorrectly Clustered Events: {self.event_incorrect_count}")
 print(f"Unannotated Events: {self.event_unannotated_count}")
 print("-" * 30)
 print(f"Total Annotated Events: {total_annotated}")
 print(f"Total Events in KB: {total_entries}\n")
 
 print("--- Performance Metrics ---")
 if total_annotated > 0:
 print(f"Clustering Accuracy: {accuracy:.2f}%")
 else:
 print("Clustering Accuracy: N/A (No annotated events found.)")
 
 print("="*50)

 def _print_session_report(self):
 """Prints a formatted report of the session grouping evaluation results."""
 total_annotated = self.session_correct_count + self.session_incorrect_count
 accuracy = (self.session_correct_count / total_annotated) * 100 if total_annotated > 0 else 0.0
 total_sessions = total_annotated + self.session_unannotated_count

 print("\n" + "="*50)
 print(" LOG SESSION GROUPING EVALUATION REPORT")
 print("="*50)
 print(f"Source Directory: {self.verification_dir}\n")

 print("--- Annotation Statistics ---")
 print(f"Correctly Grouped Sessions: {self.session_correct_count}")
 print(f"Incorrectly Grouped Sessions: {self.session_incorrect_count}")
 print(f"Unannotated Sessions: {self.session_unannotated_count}")
 print("-" * 30)
 print(f"Total Annotated Sessions: {total_annotated}")
 print(f"Total Sessions Scanned: {total_sessions}\n")

 print("--- Performance Metrics ---")
 if total_annotated > 0:
 print(f"Grouping Accuracy: {accuracy:.2f}%")
 else:
 print("Grouping Accuracy: N/A (No annotated sessions found.)")

 print("="*50 + "\n")

if __name__ == '__main__':
 config = Config()
 default_kb_path = config.kb_dir

 parser = argparse.ArgumentParser(description="Evaluate the accuracy of knowledge base event clustering and session grouping.")
 parser.add_argument(
 '--kb_dir', 
 type=str, 
 default=default_kb_path, 
 help='Directory where the knowledge base and verification files are located.'
 )
 parser.add_argument(
 '--mode',
 type=str,
 default='all',
 choices=['event', 'session', 'all'],
 help='Which evaluation to run: "event" for event clustering, "session" for session grouping, or "all" to run both.'
 )
 
 args = parser.parse_args()
 
 evaluator = KnowledgeBaseEvaluator(kb_dir=args.kb_dir)
 
 if args.mode in ['event', 'all']:
 evaluator.evaluate_events()
 
 if args.mode in ['session', 'all']:
 evaluator.evaluate_sessions()