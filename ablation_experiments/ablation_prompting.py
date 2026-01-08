PROMPT_ONE_STAGE_CODE_GEN = """
You are an expert Python programmer and log analyst. 
Your task is to write a complete, self-contained Python script to group raw logs into logical security events.

### Dataset Context ###
{dataset_context}

### Log Samples ###
{log_samples}

### Log Data Structure ###
The input `log` dictionary is a superset of fields. You MUST handle potentially missing keys gracefully.
The structure is: "{log_structure}"
You MUST use the 'Timestamp' key for any time-based calculations.

### Requirements ###
1.  **Class Name**: You must write a class named `EventProcessor`.
2.  **Self-Contained Logic**: Do NOT generate separate rule functions. Write all clustering logic (heuristics based on Time, PIDs, IP, Content Similarity, etc.) directly inside the `cluster_events` method.
3.  **Algorithm**: You should implement an efficient clustering approach (e.g., a single-pass algorithm using a Union-Find data structure or a sliding window approach).

### Method Signature Contract (MUST be followed exactly) ###

The `EventProcessor` class must adhere to the following design:

1.  **`__init__(self, logs: List[Dict])`**:
    - The constructor must accept the list of `logs`.
    - You must store these logs in `self.logs` for processing.
    ```python
    def __init__(self, logs: List[Dict]):
        self.logs = logs
        # Initialize any other state or data structures here
    ```

2.  **`cluster_events(self)`**:
    - The main clustering logic.
    - It takes NO arguments (other than `self`), as it processes the logs stored in `self.logs`.
    ```python
    def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
    ```

### Return Value Contract (MUST be followed exactly) ###
The `cluster_events` method must return a tuple `(security_events, log_index_to_event_id)`:

1.  **`security_events` (`List[List[int]]`)**:
    - A list of lists. Each inner list represents one event and contains the **original indices** (integers) of the logs in that event.
2.  **`log_index_to_event_id` (`Dict[int, int]`)**:
    - A dictionary mapping a log's original index to its event ID (the index in `security_events`).

**Example Return Value:**
If logs at indices 0, 1 form Event A, and logs at 2, 4 form Event B:
(
    [[0, 1], [2, 4]],
    {{0: 0, 1: 0, 2: 1, 4: 1}}
)

### Output ###
Provide ONLY the Python code block starting with `class EventProcessor:`. Do not include markdown formatting like "```python".
"""