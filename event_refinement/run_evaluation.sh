#!/bin/bash

# 设置要运行的次数
NUM_RUNS=10

# 获取 evaluation.py 脚本所在的目录（假设此脚本在项目根目录）
# 如果您的 evaluation.py 在子目录，请相应修改路径，例如 "event_refinement/evaluation.py"
EVAL_SCRIPT="evaluation.py" 

# 获取 config 中设置的数据集名称，用于构建目录名
DATASET_NAME="Zookeeper"

echo "Starting batch evaluation for $NUM_RUNS runs..."
echo "=================================================="

# 循环指定的次数
for i in $(seq 1 $NUM_RUNS)
do
    # 格式化数字，使其总是两位数（例如 01, 02, ..., 10）
    formatted_i=$(printf "%02d" $i)

    # 构建本次运行的 artifacts 目录后缀
    export ARTIFACTS_SUFFIX="${DATASET_NAME}_${formatted_i}"

    echo ""
    echo "--- RUN $i/$NUM_RUNS ---"
    echo "Setting artifacts directory to: event_detector/generated_processors/${ARTIFACTS_SUFFIX}"
    
    # 运行评估脚本
    # 环境变量 ARTIFACTS_SUFFIX 将被 python 脚本读取
    python "$EVAL_SCRIPT"

    echo "--- Finished RUN $i/$NUM_RUNS ---"
done

echo ""
echo "=================================================="
echo "All $NUM_RUNS evaluation runs are complete."