#!/bin/bash

# SetRuntimesNumber
NUM_RUNS=10

# Get evaluation.py InDirectory（FalsethisInDirectory）
# If evaluation.py InDirectory，Path， "event_refinement/evaluation.py"
EVAL_SCRIPT="evaluation.py" 

# Get config SetDataName，Used forBuildDirectory
DATASET_NAME="Zookeeper"

echo "Starting batch evaluation for $NUM_RUNS runs..."
echo "=================================================="

# specifytimesNumber
for i in $(seq 1 $NUM_RUNS)
do
 # Number，TotalYesNumber（ 01, 02, ..., 10）
 formatted_i=$(printf "%02d" $i)

 # BuildtimesRun artifacts Directory
 export ARTIFACTS_SUFFIX="${DATASET_NAME}_${formatted_i}"

 echo ""
 echo "--- RUN $i/$NUM_RUNS ---"
 echo "Setting artifacts directory to: event_detector/generated_processors/${ARTIFACTS_SUFFIX}"
 
 # RunEvaluate
 # ARTIFACTS_SUFFIX python 
 python "$EVAL_SCRIPT"

 echo "--- Finished RUN $i/$NUM_RUNS ---"
done

echo ""
echo "=================================================="
echo "All $NUM_RUNS evaluation runs are complete."