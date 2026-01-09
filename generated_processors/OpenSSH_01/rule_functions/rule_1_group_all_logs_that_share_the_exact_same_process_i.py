from typing import Dict, List, Optional

def rule_1_group_all_logs_that_share_the_exact_same_process_i(log: Dict) -> List[str]:
    """
    Extracts the Process ID (PID) as a linking key if it exists.
    """
    pid = log.get('PID')

    # A PID can be an integer, including 0. We proceed only if it's not None.
    if pid is not None:
        # Format the key as "KEYTYPE_keyvalue"
        return [f"PID_{pid}"]

    # If no PID is found or it is None, return an empty list.
    return []