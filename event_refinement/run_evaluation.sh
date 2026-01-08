#!/bin/bash

# Set要Run的timesNumber
NUM_RUNS=10

# Get evaluation.py 脚本所In的Directory（False设此脚本In项目根Directory）
# If您的 evaluation.py In子Directory，请相应修改Path，例如 "event_refinement/evaluation.py"
EVAL_SCRIPT="evaluation.py" 

# Get config 中Set的Data集Name，Used forBuildDirectory名
DATASET_NAME="Zookeeper"

echo "Starting batch evaluation for $NUM_RUNS runs..."
echo "=================================================="

# 循环指定的timesNumber
for i in $(seq 1 $NUM_RUNS)
do
 # 格式化Number字，使其TotalYes两位Number（例如 01, 02, ..., 10）
 formatted_i=$(printf "%02d" $i)

 # Build本timesRun的 artifacts Directory后缀
 export ARTIFACTS_SUFFIX="${DATASET_NAME}_${formatted_i}"

 echo ""
 echo "--- RUN $i/$NUM_RUNS ---"
 echo "Setting artifacts directory to: event_detector/generated_processors/${ARTIFACTS_SUFFIX}"
 
 # RunEvaluate脚本
 # 环境变量 ARTIFACTS_SUFFIX 将被 python 脚本读取
 python "$EVAL_SCRIPT"

 echo "--- Finished RUN $i/$NUM_RUNS ---"
done

echo ""
echo "=================================================="
echo "All $NUM_RUNS evaluation runs are complete."