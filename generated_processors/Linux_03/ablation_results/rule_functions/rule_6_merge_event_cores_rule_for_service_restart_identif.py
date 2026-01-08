def rule_6_merge_event_cores_rule_for_service_restart_identif(log: dict) -> list[str]:
    """
    Identifies service shutdown or startup events to be potentially merged into a 'Service Restart' event.
    The linking key is the process name.
    Self-contained 'restart.' events are ignored as they don't need linking.
    """
    keys = []

    process_name = log.get('ProcessName')
    event_template = log.get('EventTemplate', '')

    # A linking key cannot be formed without a process name.
    if not process_name:
        return []

    # Per the rule, a 'restart.' template signifies a self-contained event
    # that does not need to be linked with others. Therefore, no key is extracted.
    if event_template == 'restart.':
        return []

    # Keywords to identify shutdown and startup events from the template.
    shutdown_keywords = ['shutdown', 'stopped', 'stopping', 'down']
    startup_keywords = ['startup', 'started', 'starting', 'up']

    template_lower = event_template.lower()

    is_shutdown_event = any(keyword in template_lower for keyword in shutdown_keywords)
    is_startup_event = any(keyword in template_lower for keyword in startup_keywords)

    # If the log is a shutdown or startup event, extract the process name as a key
    # for the orchestrator to link it with its counterpart.
    if is_shutdown_event or is_startup_event:
        key = f"PROCESSNAME_{process_name}"
        keys.append(key)

    return keys