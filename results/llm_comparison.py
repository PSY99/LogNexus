# generate_comparison_chart.py

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re

def parse_model_name(filepath):
    """从文件路径中提取模型名称，例如 'deepseek-r1'"""
    dir_name = os.path.basename(os.path.dirname(filepath))
    # 假设文件夹格式为 "generated_processors_MODELNAME"
    parts = dir_name.split('_')
    if len(parts) > 2:
        return '_'.join(parts[2:])
    return "unknown"

def get_model_family(model_name):
    """从模型名称中提取模型家族，用于分组排序"""
    # 使用正则表达式匹配常见的模型族
    match = re.match(r"^(gpt|deepseek|gemini|qwen|claude)", model_name, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    # 如果没有匹配到，返回一个默认值，使其排在后面
    return "zzz_other" 

def collect_data():
    """收集并处理所有CSV文件中的数据"""
    # 查找所有符合条件的CSV文件
    file_paths = glob.glob('../generated_processors_*/Linux_mode_wise_statistics.csv')
    
    if not file_paths:
        print("错误：在 ./generated_processors_*/ 目录下没有找到任何 Linux_mode_wise_statistics.csv 文件。")
        print("请确保脚本与 'generated_processors_*' 文件夹在同一目录下运行。")
        return None

    all_data = []

    for f_path in file_paths:
        try:
            model_name = parse_model_name(f_path)
            df = pd.read_csv(f_path)
            
            # 筛选需要的行和列
            filtered_df = df[df['Mode'].isin(['full_model', 'no_refinement'])].copy()
            
            if filtered_df.empty:
                print(f"警告：文件 {f_path} 中没有找到 'full_model' 或 'no_refinement' 模式的数据。")
                continue

            # 提取ARI均值
            # 使用 .loc 避免 SettingWithCopyWarning
            filtered_df.loc[:, 'ARI_mean'] = filtered_df['Adjusted Rand Index (ARI)'].astype(str).str.split('±').str[0].astype(float)
            
            for _, row in filtered_df.iterrows():
                all_data.append({
                    'Model Name': model_name,
                    'Model Family': get_model_family(model_name),
                    'Mode': row['Mode'],
                    'ARI': row['ARI_mean']
                })
        except Exception as e:
            print(f"处理文件 {f_path} 时出错: {e}")

    if not all_data:
        print("错误：未能从任何文件中成功提取数据。")
        return None
        
    final_df = pd.DataFrame(all_data)
    
    # 根据模型家族和模型名称排序
    final_df = final_df.sort_values(by=['Model Family', 'Model Name'], ascending=[True, True])
    
    return final_df

def plot_ari_comparison(df):
    """绘制并保存ARI对比图"""
    if df is None or df.empty:
        print("没有数据可供绘图。")
        return

    # 设置绘图风格
    sns.set_theme(style="whitegrid")
    
    # 创建图表
    plt.figure(figsize=(16, 9))
    
    # 使用barplot绘制分组柱状图
    ax = sns.barplot(data=df, x='Model Name', y='ARI', hue='Mode', palette="viridis")
    
    # 添加标题和标签
    # ax.set_title('Model Performance Comparison: Adjusted Rand Index (ARI)', fontsize=20, pad=20)
    ax.set_xlabel('Model', fontsize=17, labelpad=18)
    ax.set_ylabel('Adjusted Rand Index (ARI)', fontsize=17, labelpad=18)
    ax.tick_params(axis='x', labelsize=15)  # 单独设置 X 轴标签的字体大小
    plt.xticks(rotation=45, ha='right')   # 使用 plt.xticks 设置旋转和水平对齐    ax.tick_params(axis='y', labelsize=12)
    ax.set_ylim(0.2, 1.15) # ARI的范围是-1到1，但通常在0-1之间，设置上限略高于1
    
    # 修改图例
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles, labels=['Full Model (with refinement)', 'Base Model (no refinement)'], title='Mode', fontsize=15, title_fontsize=16)

    # # 在每个柱子上方显示数值
    # for p in ax.patches:
    #     ax.annotate(format(p.get_height(), '.4f'), 
    #                 (p.get_x() + p.get_width() / 2., p.get_height()), 
    #                 ha = 'center', va = 'center', 
    #                 xytext = (0, 9), 
    #                 textcoords = 'offset points',
    #                 fontsize=10)

    # 调整布局以防止标签被截断
    plt.tight_layout()
    
    # 确保./results/目录存在
    output_dir = './'
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存图表
    save_path = os.path.join(output_dir, 'model_ari_comparison.png')
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    print(f"图表已成功保存至: {save_path}")
    
    # 显示图表
    plt.show()


if __name__ == '__main__':
    # 1. 收集数据
    processed_data = collect_data()
    
    # 2. 绘制图表
    plot_ari_comparison(processed_data)

