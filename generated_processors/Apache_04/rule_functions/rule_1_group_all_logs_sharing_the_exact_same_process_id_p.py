from typing import Dict, List

def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
 """
 Extracts a linking key from the Process ID (PID) if it exists.
 
 Rule: "Group all logs sharing the exact same Process ID (PID) into a 
 foundational 'Event Core'. This grouping is absolute and these cores 
 must never be split internally."
 """
 pid = log.get('PID')
 
 # A PID of 0 is valid, so we only check for None.
 if pid is not None:
 # Format the key as "KEYTYPE_keyvalue"
 return [f"PID_{pid}"]
 
 return []