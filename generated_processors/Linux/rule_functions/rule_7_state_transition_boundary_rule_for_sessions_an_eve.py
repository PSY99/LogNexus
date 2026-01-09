def rule_7_state_transition_boundary_rule_for_sessions_an_eve(log: Dict) -> List[str]:
    keys = []
    pid = log.get('PID', None)
    event_template = log.get('EventTemplate', '')
    parameters = log.get('Parameters', [])
    
    # Check for session opened for user
    if 'session opened for user' in event_template:
        if pid is not None:
            keys.append(f"PID_{pid}")
    
    # Check for session closed for user
    if 'session closed for user' in event_template:
        if pid is not None:
            keys.append(f"PID_{pid}")
    
    # Extract non-blacklisted parameters as linking keys
    blacklisted_words = {'root', 'admin', 'system', 'local', 'unknown', 'null'}
    for param in parameters:
        if param and param.lower() not in blacklisted_words:
            keys.append(f"PARAM_{param}")
    
    return keys