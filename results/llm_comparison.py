# generate_comparison_chart.py

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re

def parse_model_name(filepath):
 """Extract model name from file path, e.g., 'deepseek-r1'"""
 dir_name = os.path.basename(os.path.dirname(filepath))
 # Assume folder format is "generated_processors_MODELNAME"
 parts = dir_name.split('_')
 if len(parts) > 2:
 return '_'.join(parts[2:])
 return "unknown"

def get_model_family(model_name):
 """Extract model family from model name for grouping and sorting"""
 # Use regex to match common model families
 match = re.match(r"^(gpt|deepseek|gemini|qwen|claude)", model_name, re.IGNORECASE)
 if match:
 return match.group(1).lower()
 # If no match, return a default value to place it at the end
 return "zzz_other" 

def collect_data():
 """Collect and process data from all CSV files"""
 # Find all matching CSV files
 file_paths = glob.glob('../generated_processors_*/Linux_mode_wise_statistics.csv')
 
 if not file_paths:
 print("error: No Linux_mode_wise_statistics.csv files found in ./generated_processors_*/ directories.")
 print("Please ensure the script is run in the same directory as 'generated_processors_*' folders.")
 return None

 all_data = []

 for f_path in file_paths:
 try:
 model_name = parse_model_name(f_path)
 df = pd.read_csv(f_path)
 
 # Filter required rows and columns
 filtered_df = df[df['Mode'].isin(['full_model', 'no_refinement'])].copy()
 
 if filtered_df.empty:
 print(f"Warning: File {f_path} does not contain data for 'full_model' or 'no_refinement' modes.")
 continue

 # Extract ARI mean values
 # Use .loc to avoid SettingWithCopyWarning
 filtered_df.loc[:, 'ARI_mean'] = filtered_df['Adjusted Rand index (ARI)'].astype(str).str.split('±').str[0].astype(float)
 
 for _, row in filtered_df.iterrows():
 all_data.append({
 'Model Name': model_name,
 'Model Family': get_model_family(model_name),
 'Mode': row['Mode'],
 'ARI': row['ARI_mean']
 })
 except Exception as e:
 print(f"processing file {f_path} encountered error: {e}")

 if not all_data:
 print("error: Failed to extract data from any file.")
 return None
 
 final_df = pd.DataFrame(all_data)
 
 # Sort by model family and model name
 final_df = final_df.sort_values(by=['Model Family', 'Model Name'], ascending=[True, True])
 
 return final_df

def plot_ari_comparison(df):
 """Plot and save ARI comparison chart"""
 if df is None or df.empty:
 print("No data available for plotting.")
 return

 # Set plot style
 sns.set_theme(style="whitegrid")
 
 # Create chart
 plt.figure(figsize=(16, 9))
 
 # Use barplot to draw grouped bar chart
 ax = sns.barplot(data=df, x='Model Name', y='ARI', hue='Mode', palette="viridis")
 
 # Addtitleandlabel
 # ax.set_title('Model Performance Comparison: Adjusted Rand index (ARI)', fontsize=20, pad=20)
 ax.set_xlabel('Model', fontsize=17, labelpad=18)
 ax.set_ylabel('Adjusted Rand index (ARI)', fontsize=17, labelpad=18)
 ax.tick_params(axis='x', labelsize=15) # single独Set X 轴label的字体Size
 plt.xticks(rotation=45, ha='right') # Use plt.xticks Set旋转and水平对齐 ax.tick_params(axis='y', labelsize=12)
 ax.set_ylim(0.2, 1.15) # ARI的范围is-1to1，但usuallyin0-1之间，Set上限略高于1
 
 # 修改图例
 handles, labels = ax.get_legend_handles_labels()
 ax.legend(handles=handles, labels=['Full Model (with refinement)', 'Base Model (no refinement)'], title='Mode', fontsize=15, title_fontsize=16)

 # # inEach柱子上方显示NumberValue
 # for p in ax.patches:
 # ax.annotate(format(p.get_height(), '.4f'), 
 # (p.get_x() + p.get_width() / 2., p.get_height()), 
 # ha = 'center', va = 'center', 
 # xytext = (0, 9), 
 # textcoords = 'offset points',
 # fontsize=10)

 # 调整布局以防止label被截断
 plt.tight_layout()
 
 # Ensure./results/Directory存in
 output_dir = './'
 os.makedirs(output_dir, exist_ok=True)
 
 # Save图table
 save_path = os.path.join(output_dir, 'model_ari_comparison.png')
 plt.savefig(save_path, dpi=300, bbox_inches='tight')
 
 print(f"图table已SuccessSave至: {save_path}")
 
 # 显示图table
 plt.show()


if __name__ == '__main__':
 # 1. 收setData
 processed_data = collect_data()
 
 # 2. 绘制图table
 plot_ari_comparison(processed_data)

