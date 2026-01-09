def rule_2_logs_that_lack_a_pid_such_as_those_from_the_kernel(log: Dict) -> List[str]:
    pid = log.get('PID', None)
    process_name = log.get('ProcessName', '').lower()
    
    # Check if PID is missing and process name is one of the system-level ones
    if pid is None and process_name in {'kernel', 'network', 'shutdown', 'init'}:
        return ['EVENT_CORE']
    
    return []