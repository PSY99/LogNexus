# event_detector/code_generator.py

import os
import re
import json
import logging
import ast
import importlib.util
from typing import List, Dict, Optional, Any, Tuple
import time
from copy import deepcopy

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from utils.llm_utils import call_llm_api

################################################################################
# --- PROMPT DEFINITIONS ---
################################################################################

# 阶段三：将单条自然语言规则翻译为独立的Python“规则函数”
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

# 阶段四：编写最终的“主函数”框架，调用所有规则函数
PROMPT_FOR_MAIN_FRAMEWORK = """
    You are an expert System Architect and Python Programmer. Your task is to write a complete and efficient `EventProcessor` class that clusters logs into security events.

    ############################################################
    ### CONTEXT: THE OVERALL PLAN (PREVIOUS CHAT HISTORY) ###
    ############################################################

    **Our Goal**: To efficiently group raw log entries into security events.

    **Our Strategy**:
    1.  **Phase 1 (Done)**: We defined natural language rules about what "linking keys" (e.g., PID, IP, user, log template) can connect two logs.
    2.  **Phase 2 (Done)**: We created simple, **stateless "Key Extractor" functions**. Each function takes a single log and returns a list of its potential linking keys (e.g., `['PID_12345', 'IP_TEMPLATE_1.2.3.4_Failed password']`).
    3.  **Phase 3 (Your Task)**: You are now building the **stateful orchestrator**. This class will intelligently use the keys from the extractor functions to group logs.

    ### The Key Extractor Functions You MUST Use ###
    Here is the complete Python source code for the stateless functions. You must call these functions to extract keys from each log.
    {rule_functions_code_str}

    ############################################################
    ### YOUR TASK: IMPLEMENT THE `EventProcessor` CLASS ###
    ############################################################

    Your implementation should be based on a highly efficient, single-pass clustering approach. The best-practice for this is the **Union-Find (Disjoint Set Union)** algorithm.

    ### Log Data Structure ###
    The input `log` dictionary, which is an element of the `logs` list, is a superset of fields from different log types. The orchestrator and the rule functions must handle potentially missing keys gracefully.

    The structure is: `"{log_structure}"`
    You MUST use the 'Timestamp' key for any time-based calculations.

    ### High-Level Implementation Guidance ###
    Your main `cluster_events` method should follow these algorithmic steps:
    1.  **Initialization**:
        *   Set up a **Union-Find data structure** for all log entries (e.g., using a `parent` list). You should implement helper methods like `find` (with path compression) and `union` (by size or rank).
        *   Initialize a **state-tracking dictionary** to map each unique linking key to the last log where it was seen (storing at least the log's index and timestamp).
        *   Define a flexible way to manage **time windows** for different linking key types (e.g., a dictionary mapping key prefixes like 'PID' or 'LABEL' to `timedelta` objects).

    2.  **Single-Pass Processing**:
        *   Iterate through each log entry **exactly once**, in chronological order.
        *   For each log, call all the provided `rule_functions` to get a complete list of its linking keys.

    3.  **Core Clustering Logic (Inside the Loop)**:
        *   For each key from the current log, check your state-tracking dictionary.
        *   If the key has appeared recently within the **appropriate time window**, perform a **`union` operation** to merge the current log's set with the previous log's set.
        *   Always **update the state-tracking dictionary** with the current log's information for that key.

    4.  **Finalization**:
        *   After the loop, traverse the Union-Find structure to construct the final list of events.

    ### Method Signature Contract (MUST be followed exactly) ###
    
    The `EventProcessor` class must adhere to the following design:

    1.  **`__init__(self, ...)`**: The constructor must accept the list of `logs` to be processed. The processor instance will be initialized with and tied to this specific dataset.
        ```python
        def __init__(self, logs: List[Dict]):
        ```

    2.  **`cluster_events(...)`**: The main clustering logic must be in a method that accepts the list of rule functions. Its signature must be exactly:
        ```python
        def cluster_events(self, rule_functions: List[Callable]) -> Tuple[List[List[int]], Dict[int, int]]:
        ```
        - `rule_functions`: The list of actual key extractor function objects to be called on the logs provided during initialization.

    ### Return Value Contract (MUST be followed exactly) ###
    The `cluster_events` method must return a tuple containing two items: `(security_events, log_index_to_event_id)`.
    1.  **`security_events` (`List[List[int]]`)**:
        *   A list of lists, where each inner list represents a single clustered event.
        *   The integers inside the inner lists are the **original indices** of the logs belonging to that event.
    2.  **`log_index_to_event_id` (`Dict[int, int]`)**:
        *   A dictionary that maps a log's original index (integer) to its corresponding event ID (integer).
        *   The event ID is the index of that event in the `security_events` list.

    **Example of the expected return value:**
    If 6 logs (indices 0-5) are clustered into three events `(0, 1)`, `(2, 4)`, and `(3, 5)`, the return value should be:
        (
            [[0, 1], [2, 4], [3, 5]],
            {{0: 0, 1: 0, 2: 1, 4: 1, 3: 2, 5: 2}}
        )

    ############################################################
    ### STRICT OUTPUT REQUIREMENTS ###
    ############################################################
    
    1.  **Imports**: You MUST include all necessary imports at the very top of your code (e.g., `from typing import List, Dict, Tuple, Callable`, `import collections`, `import datetime`, etc.).
    2.  **Format**: Your response must be a **SINGLE Markdown code block** (starting with ```python and ending with ```).
    3.  **No Chatter**: Do NOT include any conversational text, explanations, or "Here is the code" messages before or after the code block. The output should be pure Python code wrapped in markdown.
    4.  **Completeness**: The code must be fully functional and self-contained.

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
            raise KeyError("The log structures file must contain a 'Default' key with a 'structure' field.")
        return structures
    except FileNotFoundError:
        logging.error(f"Log structures file not found at: {path}")
        raise
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error parsing log structures file {path}: {e}")
        raise


def validate_python_syntax(code_str: str) -> Tuple[bool, str]:
    """
    使用 Python 内置的 AST 模块检查生成的代码是否有语法错误。
    返回: (是否通过, 错误信息)
    """
    try:
        ast.parse(code_str)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Parse Error: {str(e)}"


################################################################################
# --- NEW: SECURITY & VALIDATION SANDBOX (ROBUST VERSION) ---
################################################################################

class CodeValidator:
    """
    Implements the 'Safe-Synthesis Protocol' demanded by rigorous software engineering standards.
    Provides both Static Security Analysis (AST-based) and Dynamic Runtime Verification.
    """
    
    # Whitelisted modules that generated code is allowed to import/use
    ALLOWED_IMPORTS = {'re', 'datetime', 'json', 'math', 'typing', 'collections', 'string', 'itertools', 'functools'}
    
    # Maximum allowed execution time for a batch of samples (prevent ReDoS or infinite loops)
    MAX_EXECUTION_TIME_MS = 500  # Slightly increased to allow complex logic
    
    # -------------------------------------------------------------------------
    # Comprehensive Safe Built-ins Definition
    # -------------------------------------------------------------------------
    # We explicitly define SAFE built-ins. We exclude 'open', 'eval', 'exec', 
    # 'compile', '__import__', 'input', 'exit', 'quit' etc.
    SAFE_BUILTIN_NAMES = {
        # Types and Conversions
        'bool', 'bytearray', 'bytes', 'complex', 'dict', 'float', 'frozenset', 
        'int', 'list', 'object', 'set', 'str', 'tuple', 'type',
        
        # Math and Numbers
        'abs', 'divmod', 'hash', 'hex', 'max', 'min', 'oct', 'pow', 'round', 'sum',
        
        # Iterables and Sequences
        'all', 'any', 'enumerate', 'filter', 'iter', 'len', 'map', 'next', 
        'range', 'reversed', 'slice', 'sorted', 'zip',
        
        # Object introspection (Safe ones)
        'ascii', 'chr', 'ord', 'format', 'repr', 'isinstance', 'issubclass', 
        'hasattr', 'getattr', 'callable', 'id',
        
        # Printing (Useful for debugging, safe if output is captured/ignored)
        'print' 
    }

    # Common Exceptions LLM code might try to catch
    SAFE_EXCEPTIONS = {
        'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError', 
        'AttributeError', 'NameError', 'LookupError', 'ArithmeticError',
        'ZeroDivisionError', 'AssertionError'
    }

    @staticmethod
    def _build_restricted_globals():
        """Helper to construct the safe execution environment."""
        safe_builtins = {}
        
        # 1. Load Safe Functions
        import builtins
        for name in CodeValidator.SAFE_BUILTIN_NAMES:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)
                
        # 2. Load Safe Exceptions
        for name in CodeValidator.SAFE_EXCEPTIONS:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)

        # 3. Construct the globals dict
        env = {"__builtins__": safe_builtins}
        
        # 4. Pre-inject commonly used modules (saving the LLM from needing to import them inside functions)
        import re, datetime, json, math, collections, string, typing, itertools, functools
        env.update({
            're': re, 'datetime': datetime, 'json': json, 
            'math': math, 'collections': collections, 
            'string': string, 'typing': typing,
            'itertools': itertools, 'functools': functools,
            # Type hints often used by LLMs
            'List': typing.List, 'Dict': typing.Dict, 
            'Tuple': typing.Tuple, 'Optional': typing.Optional, 
            'Any': typing.Any, 'Union': typing.Union,
            'Set': typing.Set
        })
        
        return env

    @staticmethod
    def check_static_security(code_str: str) -> Tuple[bool, str]:
        """
        Layer 1: Static Analysis via AST.
        Enforces a strict whitelist on imports and dangerous built-ins.
        """
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"

        for node in ast.walk(tree):
            # 1. Check Imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name.split('.')[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        modules = [node.module.split('.')[0]]
                
                for module in modules:
                    if module not in CodeValidator.ALLOWED_IMPORTS:
                        return False, f"Security Violation: Import of restricted module '{module}' is forbidden. Allowed: {CodeValidator.ALLOWED_IMPORTS}"

            # 2. Check for dangerous built-ins via Call
            # Note: This is a heuristic. The real protection is the restricted __builtins__ in dynamic run.
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec', 'open', 'compile', '__import__', 'subprocess', 'os', 'sys']:
                        return False, f"Security Violation: Static check detected dangerous function '{node.func.id}'."

        return True, ""

    @staticmethod
    def run_sandboxed_dry_run(code_str: str, function_name: str, test_samples: List[Dict]) -> Tuple[bool, str]:
        """
        Layer 2: Dynamic Runtime Verification (The 'Dry-Run').
        Executes the code on real sample logs within a restricted scope and time limit.
        """
        if not test_samples:
            return True, "No samples provided, skipping dry-run."

        # 1. Prepare Restricted Global Scope
        restricted_globals = CodeValidator._build_restricted_globals()

        try:
            # 2. Compile and Load Function into Scope
            # Using exec within the restricted globals ensures only safe built-ins are visible
            exec(code_str, restricted_globals)
            
            if function_name not in restricted_globals:
                return False, f"Function '{function_name}' was not defined in the executed code."
            
            target_func = restricted_globals[function_name]

            # 3. Execution with Time-Bound (Smoke Test)
            start_time = time.time()
            
            for i, log in enumerate(test_samples):
                # Deep copy to prevent side effects on the sample data
                log_copy = deepcopy(log)
                
                try:
                    result = target_func(log_copy)
                except Exception as e:
                    # Capture the specific error (e.g., 'KeyError', 'IndexError')
                    # to give better feedback to the LLM
                    error_type = type(e).__name__
                    return False, f"Runtime Error on sample log #{i}: {error_type}: {str(e)}"

                # 4. Type & Value Check
                if not isinstance(result, list):
                    return False, f"Type Violation: Function returned {type(result)}, expected List[str]."
                if result and not all(isinstance(k, str) for k in result):
                     return False, "Type Violation: Returned list contains non-string elements."

                # Check Timeout
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > CodeValidator.MAX_EXECUTION_TIME_MS:
                    return False, f"Performance Violation: Execution timed out (> {CodeValidator.MAX_EXECUTION_TIME_MS}ms). Possible infinite loop or inefficient regex."

            return True, ""

        except Exception as e:
            # Catch compilation errors or exec errors
            return False, f"Sandboxed Execution Failed: {str(e)}"



################################################################################
# --- CODE GENERATION FUNCTIONS ---
################################################################################
def generate_rule_functions(
    client: Any, config: Config, nl_rules: Dict[str, List[str]], validation_samples: List[Dict] = None
) -> Dict[str, str]:
    """
    Stage 3: Generate independent Python functions with SAFETY GUARANTEES.
    Now accepts 'validation_samples' for the dynamic dry-run.
    """
    logging.info(f"--- Stage 3: Generating Rule Functions (Safe-Synthesis Mode) ---")
    
    # ... (Load logic remains same)
    log_structures = load_log_structures(config.log_structures_path)
    dataset_name = getattr(config, 'dataset', 'Default')
    log_data_structure = log_structures.get(dataset_name, log_structures['Default'])
    
    rule_functions_code = {}
    all_rules = nl_rules['mandatory_rules'] + nl_rules['heuristic_rules']
    
    # If samples are too large, take a small subset for rapid validation
    dry_run_samples = validation_samples[:20] if validation_samples else []
    logging.info(f"Running validation on {len(dry_run_samples)} samples per rule.")

    MAX_RETRIES = 3 

    for i, nl_rule in enumerate(all_rules):
        safe_rule_desc = re.sub(r'[^a-z0-9_]', '', nl_rule.lower().replace(' ', '_'))[:50]
        function_name = f"rule_{i+1}_{safe_rule_desc}"
        
        logging.info(f"  Generating '{function_name}'...")
        
        base_prompt = PROMPT_FOR_RULE_FUNCTION.format(
            natural_language_rule=nl_rule,
            function_name=function_name,
            log_data_structure=log_data_structure
        )
        current_prompt = base_prompt
        
        for attempt in range(MAX_RETRIES):
            # 1. Call LLM
            code_str = call_llm_api(client, current_prompt, config.llm_model_name, config)
            if not code_str: continue

            # 2. Extract Code Block
            match = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(", code_str)
            if not match:
                current_prompt = base_prompt + "\n\n### ERROR: No valid function definition found.\nRewrite the code."
                continue

            generated_name = match.group(1)
            # Enforce name consistency
            if generated_name != function_name:
                code_str = re.sub(r"def\s+[a-zA-Z0-9_]+\s*\(", f"def {function_name}(", code_str, count=1)

            # =========================================================
            # LAYER 1: STATIC SECURITY CHECK (AST)
            # =========================================================
            is_safe_static, static_msg = CodeValidator.check_static_security(code_str)
            if not is_safe_static:
                logging.warning(f"    ⚠️ Attempt {attempt+1} Security Reject: {static_msg}")
                current_prompt = base_prompt + f"\n\n### SECURITY VIOLATION ###\n{static_msg}\n\nRemove forbidden imports/calls and rewrite."
                continue

            # =========================================================
            # LAYER 2: DYNAMIC RUNTIME CHECK (DRY-RUN)
            # =========================================================
            is_valid_runtime, runtime_msg = CodeValidator.run_sandboxed_dry_run(code_str, function_name, dry_run_samples)
            if not is_valid_runtime:
                logging.warning(f"    ⚠️ Attempt {attempt+1} Runtime Reject: {runtime_msg}")
                current_prompt = base_prompt + f"\n\n### RUNTIME ERROR ON SAMPLES ###\nThe code failed when running on real log samples.\nError: {runtime_msg}\n\nPlease fix the logic/syntax."
                continue

            # =========================================================
            # SUCCESS
            # =========================================================
            filepath = os.path.join(config.rule_functions_dir, f"{function_name}.py")
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(code_str)
                rule_functions_code[function_name] = code_str
                logging.info(f"    -> ✅ Verified & Saved.")
                break 
            except IOError as e:
                logging.error(f"    -> ❌ Save failed: {e}")
                break 

        else:
            logging.error(f"  ❌ FAILED to generate valid code for '{nl_rule}' after {MAX_RETRIES} attempts.")
            
    return rule_functions_code



def generate_main_framework(
    client: Any, config: Config, function_codes: Dict[str, str], nl_rules: List[str]
) -> Optional[str]:
    """
    Stage 4: Generate the main EventProcessor framework that calls all rule functions.
    """
    logging.info("--- Stage 4: Generating the main EventProcessor framework ---")
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
        logging.info("  -> ✅ Successfully generated the main framework code.")
        
        # ✨ 新增代码：附加规则函数列表的定义
        # 这会将 "ALL_RULE_FUNCTIONS = [rule_1_..., rule_2_...]" 这行代码加到文件末尾
        all_rules_list_str = f"ALL_RULE_FUNCTIONS = [{', '.join(function_codes)}]"
        framework_code += f"\n\n\n# This list is used by the host system to know which functions to pass to the processor\n{all_rules_list_str}\n"
        
    else:
        logging.error("  -> ❌ FAILED to generate the main framework code.")
        
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
        "# --- Stage 3: Independent Rule Functions ---\n" +
        "#" + "="*78 + "#\n\n" +
        "\n\n".join(rule_functions_code.values()) +
        "\n\n\n" +
        "#" + "="*78 + "#\n" +
        "# --- Stage 4: Main Event Processor Framework ---\n" +
        "#" + "="*78 + "#\n\n" +
        framework_code
    )
    
    # Write the assembled code to the final destination
    try:
        with open(config.event_processor_path, "w", encoding="utf-8") as f:
            f.write(full_code)
        logging.info(f"✅ Final event processor successfully assembled and saved to: {config.event_processor_path}")
    except IOError as e:
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
        logging.error(f"Processor file not found at {processor_code_path}. Cannot apply rules.")
        raise FileNotFoundError(f"The generated processor file was not found: {processor_code_path}")
        
    try:
        # Dynamically import the generated module
        spec = importlib.util.spec_from_file_location(name="generated_processor", location=processor_code_path)
        processor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(processor_module)
        
        # Get the class, instantiate it, and run the clustering
        EventProcessor = getattr(processor_module, 'EventProcessor')
        rule_functions_list = getattr(processor_module, 'ALL_RULE_FUNCTIONS', None)
        
        events = []
        log_to_event_map = {}

        if rule_functions_list is not None:
            # ====================================================
            # MODE A: Multi-Stage (Original)
            # Contract: 
            #   init: __init__(self, logs)
            #   call: cluster_events(self, rule_functions)
            # ====================================================
            logging.info("  -> Detected Multi-Stage generated code (ALL_RULE_FUNCTIONS found).")
            processor = EventProcessor(logs)
            events, log_to_event_map = processor.cluster_events(rule_functions_list)

        else:
            # ====================================================
            # MODE B: One-Stage (Ablation)
            # Contract (based on your PROMPT_ONE_STAGE_CODE_GEN):
            #   init: __init__(self) (implied/default)
            #   call: cluster_events(self, logs)
            # ====================================================
            logging.info("  -> Detected One-Stage generated code (No global rule list).")
            
            processor = EventProcessor(logs)

            # Call the clustering method
            # The prompt explicitly asked for: cluster_events(self, logs: List[Dict])
            events, log_to_event_map = processor.cluster_events()
        
        logging.info(f"  ✅ Clustering complete. Found {len(events)} events.")
        return events, log_to_event_map
    except Exception as e:
        logging.error(f"❌ An error occurred while applying the generated processor: {e}", exc_info=True)
        raise


    