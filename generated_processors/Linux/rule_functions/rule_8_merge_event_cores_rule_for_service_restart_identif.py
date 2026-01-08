def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    log_content = log.get('LogContent', '')
    process_name = log.get('ProcessName', '')
    parameters = log.get('Parameters', [])
    
    # Define shutdown patterns
    shutdown_patterns = [
        'exiting', 'terminating', 'Stopping', 'shutdown succeeded', 'exiting on signal'
    ]
    
    # Define startup patterns
    startup_patterns = [
        'starting', 'startup succeeded', 'started successfully'
    ]
    
    # Extract potential key components
    keys = []
    
    # Check for shutdown event
    if any(pattern in log_content.lower() for pattern in shutdown_patterns):
        if process_name:
            keys.append(f"PROCESS_{process_name}")
    
    # Check for startup event
    if any(pattern in log_content.lower() for pattern in startup_patterns):
        if process_name:
            keys.append(f"PROCESS_{process_name}")
    
    # Return all extracted keys (will be used by orchestrator to match within 60s)
    return keys