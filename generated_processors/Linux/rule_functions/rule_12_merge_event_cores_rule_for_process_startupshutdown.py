def rule_12_merge_event_cores_rule_for_process_startupshutdown(log: Dict) -> List[str]:
    # Extract relevant fields with defaults
    process_name = log.get('ProcessName', '').strip()
    event_template = log.get('EventTemplate', '').strip()
    timestamp = log.get('Timestamp')

    # Define keywords for startup/shutdown success events
    startup_success_keywords = ['started', 'startup succeeded', 'successfully started']
    shutdown_success_keywords = ['stopped', 'shutdown succeeded', 'successfully stopped']

    # Check if this is a startup or shutdown success event
    is_startup_success = any(kw in event_template.lower() for kw in startup_success_keywords)
    is_shutdown_success = any(kw in event_template.lower() for kw in shutdown_success_keywords)

    # Only proceed if it's a startup or shutdown success event
    if not (is_startup_success or is_shutdown_success):
        return []

    # Define common blacklisted words to filter out from parameters
    blacklisted_words = {'root', 'admin', 'user', 'system', 'daemon', 'unknown', 'local', 'localhost'}

    # Extract parameters and filter out blacklisted ones
    parameters = log.get('Parameters', [])
    filtered_params = [p for p in parameters if p.lower() not in blacklisted_words]

    # Create linking keys based on process name and template
    keys = []
    if process_name:
        # Add key based on process name and event type
        event_type = "STARTUP" if is_startup_success else "SHUTDOWN"
        keys.append(f"PROCESS_LIFECYCLE_{process_name.upper()}_{event_type}")

        # Add composite key with parameters if available
        if filtered_params:
            param_str = '_'.join(filtered_params)
            keys.append(f"PROCESS_LIFECYCLE_{process_name.upper()}_{event_type}_{param_str}")
        else:
            keys.append(f"PROCESS_LIFECYCLE_{process_name.upper()}_{event_type}")

    # Return the list of extracted keys
    return keys