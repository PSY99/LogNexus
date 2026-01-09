# generate_comparison_chart.py

import os
import glob
import pandas as pd
import re
import numpy as np # 用于处理无穷大值

def parse_model_name(filepath):
    """从文件路径中提取模型名称，例如 'deepseek-r1'"""
    dir_name = os.path.basename(os.path.dirname(filepath))
    # 假设文件夹格式为 "generated_processors_MODELNAME"
    parts = dir_name.split('_')
    if len(parts) > 2:
        return '_'.join(parts[2:])
    return "unknown"

def get_model_family(model_name):
    """从模型名称中提取模型家族，用于分组排序和分类"""
    # 使用正则表达式匹配常见的模型族
    match = re.match(r"^(gpt|deepseek|gemini|qwen|claude)", model_name, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    # 如果没有匹配到，返回一个默认值，使其排在后面
    return "zzz_other" 

def collect_data():
    """收集并处理所有CSV文件中的数据，同时提取ARI的均值和标准差"""
    file_paths = glob.glob('../generated_processors_*/Linux_mode_wise_statistics.csv')
    
    if not file_paths:
        print("错误：在 ../generated_processors_*/ 目录下没有找到任何 Linux_mode_wise_statistics.csv 文件。")
        print("请确保脚本的上一级目录中包含 'generated_processors_*' 文件夹。")
        return None

    all_data = []

    for f_path in file_paths:
        try:
            model_name = parse_model_name(f_path)
            df = pd.read_csv(f_path)
            
            filtered_df = df[df['Mode'].isin(['full_model', 'no_refinement'])].copy()
            
            if filtered_df.empty:
                print(f"警告：文件 {f_path} 中没有找到 'full_model' 或 'no_refinement' 模式的数据。")
                continue

            ari_parts = filtered_df['Adjusted Rand Index (ARI)'].astype(str).str.split('±', expand=True)
            
            filtered_df.loc[:, 'ARI_mean'] = pd.to_numeric(ari_parts[0], errors='coerce').fillna(0)
            filtered_df.loc[:, 'ARI_std'] = pd.to_numeric(ari_parts[1], errors='coerce').fillna(0)

            for _, row in filtered_df.iterrows():
                all_data.append({
                    'Model Name': model_name,
                    'Model Family': get_model_family(model_name),
                    'Mode': row['Mode'],
                    'ARI_mean': row['ARI_mean'],
                    'ARI_std': row['ARI_std']
                })
        except Exception as e:
            print(f"处理文件 {f_path} 时出错: {e}")

    if not all_data:
        print("错误：未能从任何文件中成功提取数据。")
        return None
        
    final_df = pd.DataFrame(all_data)
    
    final_df = final_df.sort_values(by=['Model Family', 'Model Name'], ascending=[True, True])
    
    return final_df

def generate_latex_table(df):
    """根据处理后的数据生成增强的LaTeX格式表格"""
    if df is None or df.empty:
        print("没有数据可供生成表格。")
        return

    # 1. 将数据从长格式转换为宽格式
    pivot_df = df.pivot_table(
        index=['Model Name', 'Model Family'], 
        columns='Mode', 
        values=['ARI_mean', 'ARI_std']
    ).reset_index()

    # **新增点**: 计算百分比提升
    base_ari = pivot_df[('ARI_mean', 'no_refinement')]
    full_ari = pivot_df[('ARI_mean', 'full_model')]
    
    # 计算提升率，并处理除以零的情况
    improvement = ((full_ari - base_ari) / base_ari) * 100
    # 将inf(无穷大)替换为NaN，然后用0填充，以防base_ari为0
    pivot_df[('Improvement', '%')] = improvement.replace([np.inf, -np.inf], np.nan).fillna(0)

    # 2. 定义开源模型家族
    open_source_families = ['deepseek', 'qwen']

    # 3. 将模型分为闭源和开源两组
    proprietary_df = pivot_df[~pivot_df['Model Family'].isin(open_source_families)]
    opensource_df = pivot_df[pivot_df['Model Family'].isin(open_source_families)]

    # **新增点**: 找出每个组别中表现最好的模型索引
    best_proprietary_idx = proprietary_df[('ARI_mean', 'full_model')].idxmax() if not proprietary_df.empty else None
    best_opensource_idx = opensource_df[('ARI_mean', 'full_model')].idxmax() if not opensource_df.empty else None

    # 4. 开始构建LaTeX字符串
    latex_string = r"""
\begin{table*}[htbp]
\centering
\caption{Comparison of Adjusted Rand Index (ARI) for Different LLMs. The 'Improvement' column shows the percentage increase of the Full Model over the Base Model. The best-performing model in each category is highlighted in \textbf{bold}.}
\label{tab:ari_comparison_enhanced}
\begin{tabular}{lccc}
\toprule
\textbf{Model} & \textbf{Base Model (no refinement)} & \textbf{Full Model (with refinement)} & \textbf{Improvement (\%)} \\
\midrule
\multicolumn{4}{c}{\textit{Proprietary LLMs}} \\
\midrule
"""
    
    # 辅助函数，用于生成表格行，并高亮最佳者
    def generate_rows(dataframe, best_index):
        rows_str = ""
        if not dataframe.empty:
            for index, row in dataframe.iterrows():
                is_best = (index == best_index)
                
                # 准备各列数据
                model_name_latex = row[('Model Name', '')].replace('_', r'\_')
                base_model_val = f"{row[('ARI_mean', 'no_refinement')]:.4f} $\pm$ {row[('ARI_std', 'no_refinement')]:.4f}"
                full_model_val = f"{row[('ARI_mean', 'full_model')]:.4f} $\pm$ {row[('ARI_std', 'full_model')]:.4f}"
                improvement_val = f"{row[('Improvement', '%')]:+.1f}\\%" # 使用+号显示正负，保留一位小数

                # 如果是最佳行，则加粗
                if is_best:
                    model_name_latex = f"\\textbf{{{model_name_latex}}}"
                    base_model_val = f"\\textbf{{{base_model_val}}}"
                    full_model_val = f"\\textbf{{{full_model_val}}}"
                    improvement_val = f"\\textbf{{{improvement_val}}}"

                rows_str += f"{model_name_latex} & {base_model_val} & {full_model_val} & {improvement_val} \\\\\n"
        else:
            rows_str = r"\multicolumn{4}{c}{No data found for this category.} \\" + "\n"
        return rows_str

    # 5. 填充闭源模型数据
    latex_string += generate_rows(proprietary_df, best_proprietary_idx)

    # 6. 添加开源模型部分的抬头
    latex_string += r"""\midrule
\multicolumn{4}{c}{\textit{Open-source LLMs}} \\
\midrule
"""

    # 7. 填充开源模型数据
    latex_string += generate_rows(opensource_df, best_opensource_idx)

    # 8. 结束表格
    latex_string += r"""\bottomrule
\end{tabular}
\end{table*}
"""

    # 9. 输出结果
    print("--- LaTeX Table Code (Enhanced Version) ---")
    print(latex_string)
    
    # 10. (可选) 保存到文件
    output_filename = 'model_ari_comparison_table_enhanced.tex'
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(latex_string)
    print(f"\n表格已成功保存至文件: {output_filename}")


if __name__ == '__main__':
    # 1. 收集和处理数据
    processed_data = collect_data()
    
    # 2. 生成并输出LaTeX表格
    generate_latex_table(processed_data)
