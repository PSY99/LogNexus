from typing import Dict, List

def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
    """
    Extracts the Process ID (PID) as a linking key.
    """
    pid = log.get('PID')
    
    # A PID of 0 is a valid process ID (often for kernel tasks).
    # The rule is to group by the *exact* same PID, so we check if it exists (is not None).
    if pid is not None:
        return [f"PID_{pid}"]
        
    return []