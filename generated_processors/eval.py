import os
import pandas as pd
import numpy as np
from glob import glob

DATASET = "OpenSSH_"

# Getall Linux_* File
dataset_dirs = glob(DATASET + "*")

# storeallData
all_data = []

# need toprocessmarkcolumn（ Mode column）
metric_columns = [
 "inference Time (ms)", "MLM Acc", "RPD Acc", "ECO Acc",
 "Adjusted Rand index (ARI)", "Normalized Mutual info (NMI)",
 "Homogeneity", "Completeness", "V-Measure",
 "Predicted Event Count", "True Event Count"
]

# Each Linux File
for dataset_dir in dataset_dirs:
 csv_path = os.path.join(dataset_dir, "ablation_results", "final_summary.csv")
 
 if not os.path.exists(csv_path):
 continue
 
 try:
 # read CSV File
 df = pd.read_csv(csv_path)
 
 # Preprocessing：processNoValue
 for col in metric_columns:
 if col in df.columns:
 # willNumberValueValue（N/A, NullString）Convertas NaN
 df[col] = pd.to_numeric(df[col], errors='coerce')
 # will -1 and NaN changeas 0
 df[col] = df[col].fillna(0).replace(-1, 0)
 
 # Addinfo（Optional,Used forDebug）
 df['source'] = dataset_dir
 
 # keepneed tocolumn
 columns_to_keep = ['Mode'] + metric_columns
 all_data.append(df[columns_to_keep])
 
 except Exception as e:
 print(f"process {csv_path} whenout: {str(e)}")
 continue

# MergeallData
if not all_data:
 print("tohas CSV File")
 exit()

combined_df = pd.concat(all_data, ignore_index=True)

# Mode GroupCalculateValueandStandard deviation
results = []
for mode, group in combined_df.groupby('Mode'):
 row = {'Mode': mode}
 
 for metric in metric_columns:
 values = group[metric].values
 mean_val = np.mean(values)
 std_val = np.std(values, ddof=1) # Standard deviation
 
 # processStandard deviationas0（-0.0000）
 if std_val < 0.00005:
 std_val = 0.0
 
 row[metric] = f"{mean_val:.4f}±{std_val:.4f}"
 
 results.append(row)

# CreateDataFrame
result_df = pd.DataFrame(results)

# Mode Sort（Optional）
mode_order = [
 'full_model', 'no_refinement', 'no_multistage', 'random_sampling',
 'uni_mamba', 'transformer', 
]
result_df['sort_key'] = result_df['Mode'].apply(lambda x: mode_order.index(x) if x in mode_order else 999)
result_df = result_df.sort_values('sort_key').drop('sort_key', axis=1)

# 
print("\n=== Mode GroupValue±Standard deviation ===")
print(result_df.to_string(index=False))

# Saveto CSV
output_path = DATASET + "mode_wise_statistics.csv"
result_df.to_csv(output_path, index=False)
print(f"\nSave: {output_path}")

# # Save LaTeX （Optional）
# latex_path = DATASET + "mode_wise_statistics.tex"
# result_df.to_latex(latex_path, index=False)
# print(f"LaTeX Save: {latex_path}")