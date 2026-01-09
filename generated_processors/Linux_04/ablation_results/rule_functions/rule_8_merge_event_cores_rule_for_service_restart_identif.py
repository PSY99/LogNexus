def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies potential service shutdown or startup events based on log content
    and extracts the process name as a linking key.
    """
    process_name = log.get('ProcessName')
    log_content = log.get('LogContent', '').lower()

    # The ProcessName is the essential linking component for this rule.
    # If it's not present, we cannot create a meaningful key.
    if not process_name:
        return []

    # Define common phrases indicating service shutdown or startup.
    shutdown_patterns = [
        'shutting down',
        'stopping',
        'exiting',
        'terminated',
        'received signal to shut down'
    ]

    startup_patterns = [
        'starting',
        'listening on',
        'ready to accept connections',
        'initialization complete',
        'service start-up',
        'startup complete'
    ]

    # Check if the log content contains any of the shutdown or startup phrases.
    is_shutdown_event = any(pattern in log_content for pattern in shutdown_patterns)
    is_startup_event = any(pattern in log_content for pattern in startup_patterns)

    # If the log represents either a potential shutdown or startup event,
    # create a key based on the process name. This key will be used by the
    # orchestrator to link the two events for the same service.
    if is_shutdown_event or is_startup_event:
        return [f"PROCESSNAME_{process_name}"]

    return []