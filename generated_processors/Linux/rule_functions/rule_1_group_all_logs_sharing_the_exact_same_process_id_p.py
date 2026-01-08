def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
 pid = log.get('PID')
 if pid is not None:
 return [f"PID_{pid}"]
 return []