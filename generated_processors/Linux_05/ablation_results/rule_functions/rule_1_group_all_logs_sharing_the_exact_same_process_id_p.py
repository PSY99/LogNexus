from typing import Dict, List, Optional

def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
 """
 Extracts the Process ID (PID) as a linking key if it exists.
 """
 pid = log.get('PID')
 
 if pid is not None:
 # The rule is to group by the exact same Process ID.
 # Format the key as "PID_value".
 return [f"PID_{pid}"]
 
 # If no PID is found in the log entry, no key can be generated.
 return []