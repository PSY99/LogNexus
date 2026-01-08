# Set number of runs 
NUM_RUNS=5

EVAL_SCRIPT="run_ablation.py" 

# Get dataset name from config for building directory name
export DATASET_NAME="OpenSSH"

echo "Starting batch evaluatfor $NUM_RUNS runs..."
echo "=================================================="

# Loop for specified number of times
for i in $(seq 1 $NUM_RUNS)
do
    # Format number to always be two digits (e.g., 01, 02, ..., 10)
    formatted_i=$(printf "%02d" $i)

    # Build artifacts directory suffix for this run
    export ARTIFACTS_SUFFIX="${DATASET_NAME}_${formatted_i}"

    echo ""
    echo "--- RUN $i/$NUM_RUNS ---"
    echo "Setting artifacts directory to: event_detector/generated_processors/${ARTIFACTS_SUFFIX}"
    
    # Run evaluation script
    # Environment variable ARTIFACTS_SUFFIX will be read by python script
    python "$EVAL_SCRIPT"

    echo "--- Finished RUN $i/$NUM_RUNS ---"
done

echo ""
echo "=================================================="
echo "All $NUM_RUNS evaluation runs are complete."