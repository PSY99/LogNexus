from typing import Dict, List

def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
 """
 Extracts a linking key based on the Process ID (PID).
 """
 pid = log.get('PID')
 
 if pid is not None:
 # The rule is to group by the exact same Process ID.
 # Create a key of the format "PID_<process_id>".
 return [f"PID_{pid}"]
 
 # If no PID is found, return an empty list as no key can be generated.
 return []