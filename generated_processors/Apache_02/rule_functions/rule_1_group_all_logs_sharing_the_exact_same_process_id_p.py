from typing import Dict, List, Optional

def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
    """
    Groups all logs sharing the exact same Process ID (PID).
    """
    pid = log.get('PID')

    # A PID of 0 can be valid, so we explicitly check for None.
    if pid is not None:
        return [f"PID_{pid}"]
    
    return []