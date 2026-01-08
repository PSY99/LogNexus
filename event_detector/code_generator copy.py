# event_detector/code_generator.py

import os
import re
import json
import logging
import ast
import importlib.util
from typing import List, Dict, Optional, Any, Tuple

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from utils.llm_utils import call_llm_api

################################################################################
# --- PROMPT DEFINITIONS ---
################################################################################

# stagethree：willsingle条自然语言Rule翻译as独立Python“RulefunctionNumber”
PROMPT_FOR_RULE_FUNCTION = """
 You are an expert Python programmer. Your task is to convert a single natural language rule into a simple, stateless "Key Extractor" function.

 ### Core Philosophy ###
 This function is a **stateless key extractor**. Its only job is to inspect a single log entry and extract a list of potential "linking keys" based on the rule. The main orchestrator will handle all state and logic based on the keys you provide.

 ### Function Signature Contract (MUST be followed exactly) ###
 `def {{function_name}}(log: Dict) -> List[str]:`

 - **Parameters**:
 - `log` (Dict): A single dictionary representing one log entry.
 - **Return Value (`List[str]`)**:
 - A list of strings. Each string is a "linking key" found in the log.
 - A key MUST be formatted as `"KEYTYPE_keyvalue"` or a composite like `"TYPE1_TYPE2_value1_value2"`. Examples: `"PID_12345"`, `"IP_1.2.3.4"`, `"IP_TEMPLATE_1.2.3.4_Failed password for %"`.
 - If no relevant keys are found according to the rule, return an **empty list `[]`**.

 ### Log Data Structure ###
 The input `log` dictionary is a superset of fields from different log types. Your function MUST handle potentially missing keys gracefully (e.g., using `log.get('key', default_value)`).

 The structure is: "{log_data_structure}"

 ### Natural Language Rule to Convert ###
 "{natural_language_rule}"

 ### Your Task ###
 Write ONLY the Python code for the function `{function_name}`.
 - Adhere strictly to the stateless philosophy and the function signature.
 - The function must NOT maintain any state.
 - Use the `KEYTYPE_keyvalue` format for all returned keys.
 - If the rule involves extracting parameters, you might need to filter out common blacklisted words.
 - Your response must start with `def` and contain nothing else.

 ### Example ###
 # For a rule: "Extract keys based on IP and Template combination."
 # The generated function for a log with IP '1.2.3.4' and Template 'Failed password for %'
 # should return a list containing a composite key: ['IP_TEMPLATE_1.2.3.4_Failed password for %']

 # For a rule: "Extract non-blacklisted parameters as linking keys."
 # For a log with Parameters=['root', 'tty1'], it might return: ['PARAM_tty1']
"""

# stage四：编写最终“主functionNumber”框架,CallallRulefunctionNumber
PROMPT_FOR_MAIN_FRAMEWORK = """
 You are an expert System Architect and Python Programmer. Your task is to write a complete and efficient `Eventprocessor` class that clusters logs into security events.

 ############################################################
 ### CONTEXT: THE OVERALL PLAN (PREVIOUS CHAT HISTORY) ###
 ############################################################

 **Our Goal**: to efficiently group raw log entries into security events.

 **Our Strategy**:
 1. **Phase 1 (Done)**: We defined natural language rules about what "linking keys" (e.g., PID, IP, user, log template) can connect two logs.
 2. **Phase 2 (Done)**: We created simple, **stateless "Key Extractor" functions**. Each function takes a single log and returns a list of its potential linking keys (e.g., `['PID_12345', 'IP_TEMPLATE_1.2.3.4_Failed password']`).
 3. **Phase 3 (Your Task)**: You are now building the **stateful orchestrator**. This class will intelligently use the keys from the extractor functions to group logs.

 ### The Key Extractor Functions You MUST Use ###
 Here is the complete Python source code for the stateless functions. You must call these functions to extract keys from each log.
 {rule_functions_code_str}

 ############################################################
 ### YOUR TASK: IMPLEMENT THE `Eventprocessor` CLASS ###
 ############################################################

 Your implementation should be based on a highly efficient, single-pass clustering approach. The best-practice for this is the **Union-Find (Disjoint Set Union)** algorithm.

 ### Log Data Structure ###
 The input `log` dictionary, which is an element of the `logs` list, is a superset of fields from different log types. The orchestrator and the rule functions must handle potentially missing keys gracefully.

 The structure is: `"{log_structure}"`
 You MUST use the 'Timestamp' key for any time-based calculations.

 ### High-Level Implementation Guidance ###
 Your main `cluster_events` method should follow these algorithmic steps:
 1. **initialization**:
 * Set up a **Union-Find data structure** for all log entries (e.g., using a `parent` list). You should implement helper methods like `find` (with path compression) and `union` (by size or rank).
 * initialize a **state-tracking dictionary** to map each unique linking key to the last log where it was seen (storing at least the log's index and timestamp).
 * Define a flexible way to manage **time windows** for different linking key types (e.g., a dictionary mapping key prefixes like 'PID' or 'LABEL' to `timedelta` objects).

 2. **Single-Pass processing**:
 * Iterate through each log entry **exactly once**, in chronological order.
 * For each log, call all the provided `rule_functions` to get a complete list of its linking keys.

 3. **Core Clustering Logic (inside the Loop)**:
 * For each key from the current log, check your state-tracking dictionary.
 * If the key has appeared recently within the **appropriate time window**, perform a **`union` operation** to merge the current log's set with the previous log's set.
 * Always **update the state-tracking dictionary** with the current log's information for that key.

 4. **Finalization**:
 * After the loop, traverse the Union-Find structure to construct the final list of events.

 ### Method Signature Contract (MUST be followed exactly) ###
 
 The `Eventprocessor` class must adhere to the following design:

 1. **`__init__(self, ...)`**: The constructor must accept the list of `logs` to be processed. The processor instance will be initialized with and tied to this specific dataset.
 ```python
 def __init__(self, logs: List[Dict]):
 ```

 2. **`cluster_events(...)`**: The main clustering logic must be in a method that accepts the list of rule functions. Its signature must be exactly:
 ```python
 def cluster_events(self, rule_functions: List[Callable]) -> Tuple[List[List[int]], Dict[int, int]]:
 ```
 - `rule_functions`: The list of actual key extractor function objects to be called on the logs provided during initialization.

 ### Return Value Contract (MUST be followed exactly) ###
 The `cluster_events` method must return a tuple containing two items: `(security_events, log_index_to_event_id)`.
 1. **`security_events` (`List[List[int]]`)**:
 * A list of lists, where each inner list represents a single clustered event.
 * The integers inside the inner lists are the **original indices** of the logs belonging to that event.
 2. **`log_index_to_event_id` (`Dict[int, int]`)**:
 * A dictionary that maps a log's original index (integer) to its corresponding event ID (integer).
 * The event ID is the index of that event in the `security_events` list.

 **Example of the expected return value:**
 If 6 logs (indices 0-5) are clustered into three events `(0, 1)`, `(2, 4)`, and `(3, 5)`, the return value should be:
 (
 [[0, 1], [2, 4], [3, 5]],
 {{0: 0, 1: 0, 2: 1, 4: 1, 3: 2, 5: 2}}
 )

 ############################################################
 ### STRICT OUTPUT REQUIREMENTS ###
 ############################################################
 
 1. **Imports**: You MUST include all necessary imports at the very top of your code (e.g., `from typing import List, Dict, Tuple, Callable`, `import collections`, `import datetime`, etc.).
 2. **Format**: Your response must be a **SINGLE Markdown code block** (starting with ```python and ending with ```).
 3. **No Chatter**: Do NOT include any conversational text, explanations, or "Here is the code" messages before or after the code block. The output should be pure Python code wrapped in markdown.
 4. **Completeness**: The code must be fully functional and self-contained.

 **START YOUR RESPONSE DIRECTLY WITH:** ```python
"""



def load_log_structures(path: str) -> Dict[str, str]:
 """
 Loads the log structure definitions from a JSON file.
 The JSON file should map dataset names to their structure descriptions.
 """
 try:
 with open(path, 'r', encoding='utf-8') as f:
 data = json.load(f)
 
 # --- FIX START ---
 # The original code failed if a top-level value in the JSON was not a dictionary.
 # This new version is more robust. It first checks if a value is a dictionary
 # before trying to access its 'structure' key.
 structures = {
 key: value['structure']
 for key, value in data.items()
 if isinstance(value, dict) and 'structure' in value
 }
 # --- FIX END ---

 if 'Default' not in structures:
 # This check is now more reliable since 'structures' will only contain valid entries.
 raise Keyerror("The log structures file must contain a 'Default' key with a 'structure' field.")
 return structures
 except FileNotFounderror:
 logging.error(f"Log structures file not found at: {path}")
 raise
 except (json.JSONDecodeerror, Keyerror) as e:
 logging.error(f"error parsing log structures file {path}: {e}")
 raise


################################################################################
# --- CODE GENERATION FUNCTIONS ---
################################################################################
def generate_rule_functions(
 client: Any, config: Config, nl_rules: List[str]
) -> Dict[str, str]:
 """
 Stage 3: For each natural language rule, generate an independent Python function.
 """
 logging.info(f"--- Stage 3: Generating {len(nl_rules['mandatory_rules'])} mandatory rule functions and {len(nl_rules['heuristic_rules'])} heuristic rule functions ---")

 log_structures = load_log_structures(config.log_structures_path)
 dataset_name = getattr(config, 'dataset', 'Default')
 log_data_structure = log_structures.get(dataset_name, log_structures['Default'])
 logging.info(f"Using log data structure for dataset: '{dataset_name}'")

 rule_functions_code = {}
 all_rules = nl_rules['mandatory_rules'] + nl_rules['heuristic_rules']

 for i, nl_rule in enumerate(all_rules):
 # Create a safe and descriptive function name
 safe_rule_desc = re.sub(r'[^a-z0-9_]', '', nl_rule.lower().replace(' ', '_'))[:50]
 function_name = f"rule_{i+1}_{safe_rule_desc}"
 
 logging.info(f" Generating function '{function_name}' for rule: '{nl_rule}'")
 
 prompt = PROMPT_FOR_RULE_FUNCTION.format(
 natural_language_rule=nl_rule,
 function_name=function_name,
 log_data_structure=log_data_structure
 )
 
 code_str = call_llm_api(client, prompt, config.llm_model_name, config)
 
 if code_str:
 match = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(", code_str)
 if match:
 generated_name = match.group(1)
 if generated_name != function_name:
 logging.warning(f" ⚠️ Function name mismatch! LLM wrote '{generated_name}', enforcing '{function_name}'")
 # 只替换定义处名字 (count=1),避免误伤其他content
 code_str = re.sub(r"def\s+[a-zA-Z0-9_]+\s*\(", f"def {function_name}(", code_str, count=1)
 else:
 # If连 def 都找不to,说明Generated code完全不可用
 logging.error(f" ❌ invalid code structure generated for {function_name}")
 continue

 # Persist the individual rule function for debugging
 filepath = os.path.join(config.rule_functions_dir, f"{function_name}.py")
 try:
 with open(filepath, 'w', encoding='utf-8') as f:
 f.write(code_str)
 rule_functions_code[function_name] = code_str
 logging.info(f" -> ✅ Success. Saved to {filepath}")
 except IOerror as e:
 logging.error(f" -> ❌ FAILED to save rule function to {filepath}: {e}")
 else:
 logging.warning(f" -> ❌ FAILED to generate code for rule: {nl_rule}")
 
 return rule_functions_code


def generate_main_framework(
 client: Any, config: Config, function_codes: Dict[str, str], nl_rules: List[str]
) -> Optional[str]:
 """
 Stage 4: Generate the main Eventprocessor framework that calls all rule functions.
 """
 logging.info("--- Stage 4: Generating the main Eventprocessor framework ---")
 log_structures = load_log_structures(config.log_structures_path)
 dataset_name = getattr(config, 'dataset', 'Default')
 log_data_structure = log_structures.get(dataset_name, log_structures['Default'])

 all_functions_str = "\n\n".join(function_codes.values())

 prompt = PROMPT_FOR_MAIN_FRAMEWORK.format(
 rule_functions_code_str=all_functions_str,
 log_structure=log_data_structure
 )
 
 framework_code = call_llm_api(client, prompt, config.llm_model_name, config)
 
 if framework_code:
 logging.info(" -> ✅ Successfully generated the main framework code.")
 
 # ✨ Newnewcode：附加RulefunctionNumberList定义
 # 这会will "ALL_RULE_FUNCTIONS = [rule_1_..., rule_2_...]" 这linecode加toFile末尾
 all_rules_list_str = f"ALL_RULE_FUNCTIONS = [{', '.join(function_codes)}]"
 framework_code += f"\n\n\n# This list is used by the host system to know which functions to pass to the processor\n{all_rules_list_str}\n"
 
 else:
 logging.error(" -> ❌ FAILED to generate the main framework code.")
 
 return framework_code


def assemble_full_processor_file(
 config: Config,
 rule_functions_code: Dict[str, str],
 framework_code: str
):
 """
 Assemble all generated code parts into a single, final, executable Python file.
 """
 logging.info("--- Assembling final processor file ---")
 
 # Define the header for the final script
 header = [
 "# This file was auto-generated by the Meta-Programmed Detector on " + logging.time.strftime("%Y-%m-%d %H:%M:%S"),
 "# It contains event detection logic dynamically created by an LLM based on provided rules.",
 "# DO NOT EDIT THIS FILE MANUALLY.",
 "",
 "from typing import List, Dict, Optional, Tuple, Any",
 "from collections import defaultdict",
 "\n"
 ]
 
 # Combine header, all rule functions, and the main framework
 full_code = (
 "\n".join(header) +
 "#" + "="*78 + "#\n" +
 "# --- Stage 3: independent Rule Functions ---\n" +
 "#" + "="*78 + "#\n\n" +
 "\n\n".join(rule_functions_code.values()) +
 "\n\n\n" +
 "#" + "="*78 + "#\n" +
 "# --- Stage 4: Main Event processor Framework ---\n" +
 "#" + "="*78 + "#\n\n" +
 framework_code
 )
 
 # Write the assembled code to the final destination
 try:
 with open(config.event_processor_path, "w", encoding="utf-8") as f:
 f.write(full_code)
 logging.info(f"✅ Final event processor successfully assembled and saved to: {config.event_processor_path}")
 except IOerror as e:
 logging.error(f"❌ Failed to write final processor file: {e}")
 raise


def apply_and_cluster_events(logs: List[Dict[str, Any]], processor_code_path: str) -> Tuple[List[List[int]], Dict[int, int]]:
 """
 Dynamically load and run the generated event processor to cluster logs.
 
 MODIFIED: Now supports both:
 1. Multi-Stage Mode: Expects 'ALL_RULE_FUNCTIONS' and class init with logs.
 2. One-Stage Mode (Ablation): Expects no global rules list and method call with logs.
 """
 logging.info("--- Application Phase: Applying generated code to cluster logs ---")
 
 if not os.path.exists(processor_code_path):
 logging.error(f"processor file not found at {processor_code_path}. Cannot apply rules.")
 raise FileNotFounderror(f"The generated processor file was not found: {processor_code_path}")
 
 try:
 # Dynamically import the generated module
 spec = importlib.util.spec_from_file_location(name="generated_processor", location=processor_code_path)
 processor_module = importlib.util.module_from_spec(spec)
 spec.loader.exec_module(processor_module)
 
 # Get the class, instantiate it, and run the clustering
 Eventprocessor = getattr(processor_module, 'Eventprocessor')
 rule_functions_list = getattr(processor_module, 'ALL_RULE_FUNCTIONS', None)
 
 events = []
 log_to_event_map = {}

 if rule_functions_list is not None:
 # ====================================================
 # MODE A: Multi-Stage (Original)
 # Contract: 
 # init: __init__(self, logs)
 # call: cluster_events(self, rule_functions)
 # ====================================================
 logging.info(" -> Detected Multi-Stage generated code (ALL_RULE_FUNCTIONS found).")
 processor = Eventprocessor(logs)
 events, log_to_event_map = processor.cluster_events(rule_functions_list)

 else:
 # ====================================================
 # MODE B: One-Stage (Ablation)
 # Contract (based on your PROMPT_ONE_STAGE_CODE_GEN):
 # init: __init__(self) (implied/default)
 # call: cluster_events(self, logs)
 # ====================================================
 logging.info(" -> Detected One-Stage generated code (No global rule list).")
 
 processor = Eventprocessor(logs)

 # Call the clustering method
 # The prompt explicitly asked for: cluster_events(self, logs: List[Dict])
 events, log_to_event_map = processor.cluster_events()
 
 logging.info(f" ✅ Clustering complete. Found {len(events)} events.")
 return events, log_to_event_map
 except Exception as e:
 logging.error(f"❌ An error occurred while applying the generated processor: {e}", exc_info=True)
 raise


 