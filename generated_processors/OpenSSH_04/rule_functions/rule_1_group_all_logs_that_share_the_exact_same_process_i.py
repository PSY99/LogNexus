from typing import Dict, List

def rule_1_group_all_logs_that_share_the_exact_same_process_i(log: Dict) -> List[str]:
 """
 Groups all logs that share the exact same Process ID (PID).
 """
 pid = log.get('PID')

 # A PID must exist to form a group. The value can be an integer (including 0),
 # so we explicitly check for None.
 if pid is not None:
 # Format the key as "KEYTYPE_keyvalue"
 return [f"PID_{pid}"]

 # If no PID is found, return an empty list as per the contract.
 return []