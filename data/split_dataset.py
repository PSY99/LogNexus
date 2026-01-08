import os
import pandas as pd
import logging
import argparse
from typing import List
import itertools

# --- MODIFICATION START ---
# 1. modifiedvariablenameUpdate，Newuse

# splitRatio
TRAIN_RATIO = 0.6
ONLINE_EVAL_RATIO = 0.1 # GUARD_RATIO，inUsed forCreateinEvaluateset
TEST_RATIO = 0.3

# newoneprocesslineNumber
MAX_LINES_TO_PROCESS = 80000

# EnsureRatiototalandas1
assert TRAIN_RATIO + ONLINE_EVAL_RATIO + TEST_RATIO == 1.0, "Ratios must sum to 1.0"
# --- MODIFICATION END ---

def get_files_to_split(dataset_dir: str, dataset_name: str) -> List[str]:
 """
 According toDatasetName，Findallneed tosamestepSplitkeyFile。
 """
 base_filename = f"{dataset_name}_full"
 potential_files = [
 os.path.join(dataset_dir, base_filename + '.log'),
 os.path.join(dataset_dir, base_filename + '.log_structured.csv'),
 ]

 existing_files = [f for f in potential_files if os.path.exists(f)]
 logging.info(f"Found {len(existing_files)} related files to split for dataset '{dataset_name}'.")
 for f in existing_files:
 logging.info(f" - {os.path.basename(f)}")
 
 if not existing_files:
 raise FileNotFounderror(f"No source files found for dataset '{dataset_name}' in directory '{dataset_dir}'. "
 f"Please ensure files like '{dataset_name}_full.log' exist.")
 
 return existing_files

def split_dataset(dataset_name: str, project_dir: str):
 """
 specifyDatasetExecutewhensplit，GenerateTraining set、inEvaluatesetandTest set。
 functionNumbersamestepprocessallkeyLogFile（、structure）。

 Args:
 dataset_name (str): processDatasetName ( 'Linux', 'OpenSSH').
 project_dir (str): Directory.
 """
 logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
 logging.info(f"--- Starting dataset split for '{dataset_name}' ---")

 # 1. BuildPathtoallkeyFile
 dataset_dir = os.path.join(project_dir, 'data', dataset_name)
 files_to_process = get_files_to_split(dataset_dir, dataset_name)

 # 2. determinesplit
 primary_file = os.path.join(dataset_dir, f"{dataset_name}_full.log_structured.csv")
 if not os.path.exists(primary_file):
 primary_file = files_to_process[0]
 logging.warning(f"'{os.path.basename(primary_file)}' not found. Using '{os.path.basename(files_to_process[0])}' to determine line count.")

 logging.info(f"Calculating split points based on '{os.path.basename(primary_file)}'...")
 
 try:
 df = pd.read_csv(primary_file, header=0 if primary_file.endswith('.csv') else None, on_bad_lines='warn')
 original_total_lines = len(df)
 except Exception:
 with open(primary_file, 'r', encoding='utf-8') as f:
 original_total_lines = sum(1 for line in f)
 if primary_file.endswith('.csv'):
 original_total_lines -=1

 effective_total_lines = min(original_total_lines, MAX_LINES_TO_PROCESS)

 if original_total_lines > effective_total_lines:
 logging.info(f"Original dataset has {original_total_lines} lines. Capping to the first {effective_total_lines} lines for splitting.")
 else:
 logging.info(f"Dataset has {original_total_lines} lines, which is within the {MAX_LINES_TO_PROCESS} limit. Using all lines.")

 # --- MODIFICATION START ---
 # 2. UpdatesplitCalculateandLog
 # based onhaslineNumberCalculatesplit
 train_end_line = int(effective_total_lines * TRAIN_RATIO)
 online_eval_end_line = int(effective_total_lines * (TRAIN_RATIO + ONLINE_EVAL_RATIO))

 logging.info(f"Effective data lines for splitting (excluding header): {effective_total_lines}")
 logging.info(f"Train set: lines 0 to {train_end_line - 1} ({train_end_line} lines)")
 logging.info(f"Online Eval set: lines {train_end_line} to {online_eval_end_line - 1} ({online_eval_end_line - train_end_line} lines)")
 logging.info(f"Test set: lines {online_eval_end_line} to {effective_total_lines - 1} ({effective_total_lines - online_eval_end_line} lines)")
 # --- MODIFICATION END ---

 # 3. EachFileExecutesplit
 for file_path in files_to_process:
 logging.info(f"processing file: {os.path.basename(file_path)}...")
 
 header = ''
 is_csv = file_path.endswith('.csv')

 with open(file_path, 'r', encoding='utf-8') as f:
 if is_csv:
 header = f.readline()
 lines = list(itertools.islice(f, effective_total_lines))

 # --- MODIFICATION START ---
 # 3. new online_eval splitandSave
 # According toCalculateoutlineNumberlinesplit
 train_lines = lines[:train_end_line]
 online_eval_lines = lines[train_end_line:online_eval_end_line] # New
 test_lines = lines[online_eval_end_line:]

 # OutputFilePath
 base, ext = os.path.splitext(os.path.basename(file_path).replace('_full', ''))
 train_file_path = os.path.join(dataset_dir, f"{base}_train{ext}")
 online_eval_file_path = os.path.join(dataset_dir, f"{base}_online_eval{ext}") # NewPath
 test_file_path = os.path.join(dataset_dir, f"{base}_test{ext}")

 # WriteTraining setFile
 with open(train_file_path, 'w', encoding='utf-8') as f:
 if is_csv and header:
 f.write(header)
 f.writelines(train_lines)
 logging.info(f" -> Saved train set to {os.path.basename(train_file_path)} ({len(train_lines)} lines)")

 # New：inEvaluatesetFile
 with open(online_eval_file_path, 'w', encoding='utf-8') as f:
 if is_csv and header:
 f.write(header)
 f.writelines(online_eval_lines)
 logging.info(f" -> Saved online eval set to {os.path.basename(online_eval_file_path)} ({len(online_eval_lines)} lines)")

 # WriteTest setFile
 with open(test_file_path, 'w', encoding='utf-8') as f:
 if is_csv and header:
 f.write(header)
 f.writelines(test_lines)
 logging.info(f" -> Saved test set to {os.path.basename(test_file_path)} ({len(test_lines)} lines)")
 # --- MODIFICATION END ---

 logging.info(f"--- Dataset split for '{dataset_name}' completed successfully! ---")

if __name__ == '__main__':
 parser = argparse.ArgumentParser(
 description="Split log datasets into training, online evaluation, and testing sets based on chronological order.",
 formatter_class=argparse.RawTextHelpFormatter
 )
 parser.add_argument(
 '--dataset',
 required=True,
 type=str,
 help="The name of the dataset to split (e.g., 'Linux', 'OpenSSH', 'BGL')."
 )
 
 default_project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
 
 parser.add_argument(
 '--project_dir',
 type=str,
 default=default_project_dir,
 help="The root directory of the project.\n(default: automatically detected as %(default)s)"
 )

 args = parser.parse_args()

 try:
 split_dataset(dataset_name=args.dataset, project_dir=args.project_dir)
 except FileNotFounderror as e:
 logging.error(str(e))
 except Exception as e:
 logging.error(f"An unexpected error occurred: {e}", exc_info=True)