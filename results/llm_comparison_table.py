# generate_comparison_chart.py

import os
import glob
import pandas as pd
import re
import numpy as np # Used forprocessNoexhaustivelargeValue

def parse_model_name(filepath):
 """Extract model name from file path, e.g., 'deepseek-r1'"""
 dir_name = os.path.basename(os.path.dirname(filepath))
 # Assume folder format is "generated_processors_MODELNAME"
 parts = dir_name.split('_')
 if len(parts) > 2:
 return '_'.join(parts[2:])
 return "unknown"

def get_model_family(model_name):
 """fromModelNameinExtractModel家族，Used forGroupSortand分类"""
 # Use regex to match common model families
 match = re.match(r"^(gpt|deepseek|gemini|qwen|claude)", model_name, re.IGNORECASE)
 if match:
 return match.group(1).lower()
 # If no match, return a default value to place it at the end
 return "zzz_other" 

def collect_data():
 """收set并processallCSVFilein的Data，samewhenExtractARI的均ValueandStandard deviation"""
 file_paths = glob.glob('../generated_processors_*/Linux_mode_wise_statistics.csv')
 
 if not file_paths:
 print("error：in ../generated_processors_*/ Directory下没has找to任何 Linux_mode_wise_statistics.csv File。")
 print("请Ensure脚本的上one级Directoryin包含 'generated_processors_*' File夹。")
 return None

 all_data = []

 for f_path in file_paths:
 try:
 model_name = parse_model_name(f_path)
 df = pd.read_csv(f_path)
 
 filtered_df = df[df['Mode'].isin(['full_model', 'no_refinement'])].copy()
 
 if filtered_df.empty:
 print(f"Warning: File {f_path} does not contain data for 'full_model' or 'no_refinement' modes.")
 continue

 ari_parts = filtered_df['Adjusted Rand index (ARI)'].astype(str).str.split('±', expand=True)
 
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
 print(f"processing file {f_path} encountered error: {e}")

 if not all_data:
 print("error: Failed to extract data from any file.")
 return None
 
 final_df = pd.DataFrame(all_data)
 
 final_df = final_df.sort_values(by=['Model Family', 'Model Name'], ascending=[True, True])
 
 return final_df

def generate_latex_table(df):
 """According toprocess后的DataGeneratenew强的LaTeX格式table格"""
 if df is None or df.empty:
 print("没hasData可供Generatetable格。")
 return

 # 1. willDatafrom长格式Convertas宽格式
 pivot_df = df.pivot_table(
 index=['Model Name', 'Model Family'], 
 columns='Mode', 
 values=['ARI_mean', 'ARI_std']
 ).reset_index()

 # **Newnew点**: CalculatePercentage提升
 base_ari = pivot_df[('ARI_mean', 'no_refinement')]
 full_ari = pivot_df[('ARI_mean', 'full_model')]
 
 # Calculate提升率，并process除以零的情况
 improvement = ((full_ari - base_ari) / base_ari) * 100
 # willinf(Noexhaustivelarge)替换asNaN，然后用0填充，以防base_arias0
 pivot_df[('Improvement', '%')] = improvement.replace([np.inf, -np.inf], np.nan).fillna(0)

 # 2. 定义开源Model家族
 open_source_families = ['deepseek', 'qwen']

 # 3. willModel分as闭源and开源两组
 proprietary_df = pivot_df[~pivot_df['Model Family'].isin(open_source_families)]
 opensource_df = pivot_df[pivot_df['Model Family'].isin(open_source_families)]

 # **Newnew点**: 找出Each组别intable现最好的Modelindex
 best_proprietary_idx = proprietary_df[('ARI_mean', 'full_model')].idxmax() if not proprietary_df.empty else None
 best_opensource_idx = opensource_df[('ARI_mean', 'full_model')].idxmax() if not opensource_df.empty else None

 # 4. startBuildLaTeXString
 latex_string = r"""
\begin{table*}[htbp]
\centering
\caption{Comparison of Adjusted Rand index (ARI) for Different LLMs. The 'Improvement' column shows the percentage increase of the Full Model over the Base Model. The best-performing model in each category is highlighted in \textbf{bold}.}
\label{tab:ari_comparison_enhanced}
\begin{tabular}{lccc}
\toprule
\textbf{Model} & \textbf{Base Model (no refinement)} & \textbf{Full Model (with refinement)} & \textbf{Improvement (\%)} \\
\midrule
\multicolumn{4}{c}{\textit{Proprietary LLMs}} \\
\midrule
"""
 
 # auxiliaryfunctionNumber，Used forGeneratetable格line，并高亮最佳者
 def generate_rows(dataframe, best_index):
 rows_str = ""
 if not dataframe.empty:
 for index, row in dataframe.iterrows():
 is_best = (index == best_index)
 
 # prepare备各columnData
 model_name_latex = row[('Model Name', '')].replace('_', r'\_')
 base_model_val = f"{row[('ARI_mean', 'no_refinement')]:.4f} $\pm$ {row[('ARI_std', 'no_refinement')]:.4f}"
 full_model_val = f"{row[('ARI_mean', 'full_model')]:.4f} $\pm$ {row[('ARI_std', 'full_model')]:.4f}"
 improvement_val = f"{row[('Improvement', '%')]:+.1f}\\%" # Use+号显示positive负，keepone位小Number

 # Ifis最佳line，then加粗
 if is_best:
 model_name_latex = f"\\textbf{{{model_name_latex}}}"
 base_model_val = f"\\textbf{{{base_model_val}}}"
 full_model_val = f"\\textbf{{{full_model_val}}}"
 improvement_val = f"\\textbf{{{improvement_val}}}"

 rows_str += f"{model_name_latex} & {base_model_val} & {full_model_val} & {improvement_val} \\\\\n"
 else:
 rows_str = r"\multicolumn{4}{c}{No data found for this category.} \\" + "\n"
 return rows_str

 # 5. 填充闭源ModelData
 latex_string += generate_rows(proprietary_df, best_proprietary_idx)

 # 6. Add开源Model部分的抬头
 latex_string += r"""\midrule
\multicolumn{4}{c}{\textit{Open-source LLMs}} \\
\midrule
"""

 # 7. 填充开源ModelData
 latex_string += generate_rows(opensource_df, best_opensource_idx)

 # 8. Endtable格
 latex_string += r"""\bottomrule
\end{tabular}
\end{table*}
"""

 # 9. Output结果
 print("--- LaTeX Table Code (Enhanced Version) ---")
 print(latex_string)
 
 # 10. (Optional) SavetoFile
 output_filename = 'model_ari_comparison_table_enhanced.tex'
 with open(output_filename, 'w', encoding='utf-8') as f:
 f.write(latex_string)
 print(f"\ntable格已SuccessSave至File: {output_filename}")


if __name__ == '__main__':
 # 1. 收setandprocessData
 processed_data = collect_data()
 
 # 2. Generate并OutputLaTeXtable格
 generate_latex_table(processed_data)
