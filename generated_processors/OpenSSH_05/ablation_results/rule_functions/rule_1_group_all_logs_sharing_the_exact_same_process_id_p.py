from typing import Dict, List, Optional

def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
 """
 Groups all logs sharing the exact same Process ID (PID).
 """
 pid = log.get('PID')
 
 # A PID can be an integer, including 0. We check if it's not None.
 if pid is not None:
 # Format the key as "KEYTYPE_keyvalue"
 return [f"PID_{pid}"]
 
 return []