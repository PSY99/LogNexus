import os
import pandas as pd
import numpy as np
from glob import glob

DATASET = "OpenSSH_"

# 获取所有 Linux_* 文件夹
dataset_dirs = glob(DATASET + "*")

# 存储所有数据
all_data = []

# 定义需要处理的指标列（排除 Mode 列）
metric_columns = [
    "Inference Time (ms)", "MLM Acc", "RPD Acc", "ECO Acc",
    "Adjusted Rand Index (ARI)", "Normalized Mutual Info (NMI)",
    "Homogeneity", "Completeness", "V-Measure",
    "Predicted Event Count", "True Event Count"
]

# 遍历每个 Linux 文件夹
for dataset_dir in dataset_dirs:
    csv_path = os.path.join(dataset_dir, "ablation_results", "final_summary.csv")
    
    if not os.path.exists(csv_path):
        continue
    
    try:
        # 读取 CSV 文件
        df = pd.read_csv(csv_path)
        
        # 预处理：处理无效值
        for col in metric_columns:
            if col in df.columns:
                # 将非数值值（N/A, 空字符串等）转换为 NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # 将 -1 和 NaN 替换为 0
                df[col] = df[col].fillna(0).replace(-1, 0)
        
        # 添加来源信息（可选，用于调试）
        df['source'] = dataset_dir
        
        # 仅保留需要的列
        columns_to_keep = ['Mode'] + metric_columns
        all_data.append(df[columns_to_keep])
    
    except Exception as e:
        print(f"处理 {csv_path} 时出错: {str(e)}")
        continue

# 合并所有数据
if not all_data:
    print("未找到有效的 CSV 文件")
    exit()

combined_df = pd.concat(all_data, ignore_index=True)

# 按 Mode 分组计算均值和标准差
results = []
for mode, group in combined_df.groupby('Mode'):
    row = {'Mode': mode}
    
    for metric in metric_columns:
        values = group[metric].values
        mean_val = np.mean(values)
        std_val = np.std(values, ddof=1)  # 样本标准差
        
        # 处理标准差为0的情况（避免显示-0.0000）
        if std_val < 0.00005:
            std_val = 0.0
        
        row[metric] = f"{mean_val:.4f}±{std_val:.4f}"
    
    results.append(row)

# 创建结果DataFrame
result_df = pd.DataFrame(results)

# 按 Mode 排序（可选）
mode_order = [
    'full_model', 'no_refinement', 'no_multistage', 'random_sampling',
    'uni_mamba', 'transformer', 
]
result_df['sort_key'] = result_df['Mode'].apply(lambda x: mode_order.index(x) if x in mode_order else 999)
result_df = result_df.sort_values('sort_key').drop('sort_key', axis=1)

# 打印结果
print("\n=== 按 Mode 分组的均值±标准差统计 ===")
print(result_df.to_string(index=False))

# 保存结果到 CSV
output_path = DATASET + "mode_wise_statistics.csv"
result_df.to_csv(output_path, index=False)
print(f"\n结果已保存至: {output_path}")

# # 保存 LaTeX 格式（可选）
# latex_path = DATASET + "mode_wise_statistics.tex"
# result_df.to_latex(latex_path, index=False)
# print(f"LaTeX 格式已保存至: {latex_path}")