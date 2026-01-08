def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: dict) -> list[str]:
 """
 Extracts the Process ID (PID) as a linking key.
 This rule groups all logs sharing the exact same PID.
 """
 pid = log.get('PID')
 if pid is not None:
 return [f"PID_{pid}"]
 return []