import os
import pandas as pd
import numpy as np
from glob import glob

DATASET = "OpenSSH_"

# Getall Linux_* File夹
dataset_dirs = glob(DATASET + "*")

# 存储allData
all_data = []

# 定义need toprocess指标column（排除 Mode column）
metric_columns = [
 "inference Time (ms)", "MLM Acc", "RPD Acc", "ECO Acc",
 "Adjusted Rand index (ARI)", "Normalized Mutual info (NMI)",
 "Homogeneity", "Completeness", "V-Measure",
 "Predicted Event Count", "True Event Count"
]

# 遍历Each Linux File夹
for dataset_dir in dataset_dirs:
 csv_path = os.path.join(dataset_dir, "ablation_results", "final_summary.csv")
 
 if not os.path.exists(csv_path):
 continue
 
 try:
 # read CSV File
 df = pd.read_csv(csv_path)
 
 # Preprocessing：processNo效Value
 for col in metric_columns:
 if col in df.columns:
 # will非NumberValueValue（N/A, NullString等）Convertas NaN
 df[col] = pd.to_numeric(df[col], errors='coerce')
 # will -1 and NaN 替换as 0
 df[col] = df[col].fillna(0).replace(-1, 0)
 
 # Add来源info（Optional,Used forDebug）
 df['source'] = dataset_dir
 
 # 仅keepneed tocolumn
 columns_to_keep = ['Mode'] + metric_columns
 all_data.append(df[columns_to_keep])
 
 except Exception as e:
 print(f"process {csv_path} when出错: {str(e)}")
 continue

# MergeallData
if not all_data:
 print("未找tohas效 CSV File")
 exit()

combined_df = pd.concat(all_data, ignore_index=True)

# 按 Mode GroupCalculate均ValueandStandard deviation
results = []
for mode, group in combined_df.groupby('Mode'):
 row = {'Mode': mode}
 
 for metric in metric_columns:
 values = group[metric].values
 mean_val = np.mean(values)
 std_val = np.std(values, ddof=1) # 样本Standard deviation
 
 # processStandard deviationas0情况（避免显示-0.0000）
 if std_val < 0.00005:
 std_val = 0.0
 
 row[metric] = f"{mean_val:.4f}±{std_val:.4f}"
 
 results.append(row)

# Create结果DataFrame
result_df = pd.DataFrame(results)

# 按 Mode Sort（Optional）
mode_order = [
 'full_model', 'no_refinement', 'no_multistage', 'random_sampling',
 'uni_mamba', 'transformer', 
]
result_df['sort_key'] = result_df['Mode'].apply(lambda x: mode_order.index(x) if x in mode_order else 999)
result_df = result_df.sort_values('sort_key').drop('sort_key', axis=1)

# 打印结果
print("\n=== 按 Mode Group均Value±Standard deviation统计 ===")
print(result_df.to_string(index=False))

# Save结果to CSV
output_path = DATASET + "mode_wise_statistics.csv"
result_df.to_csv(output_path, index=False)
print(f"\n结果已Save至: {output_path}")

# # Save LaTeX 格式（Optional）
# latex_path = DATASET + "mode_wise_statistics.tex"
# result_df.to_latex(latex_path, index=False)
# print(f"LaTeX 格式已Save至: {latex_path}")