def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    process_name = log.get('ProcessName')
    event_template = log.get('EventTemplate', '')

    if not process_name:
        return []

    # Keywords indicating a service shutdown or startup, derived from the rule's examples.
    # e.g., 'exiting', 'shutdown succeeded', 'starting BIND', 'startup succeeded'
    shutdown_keywords = ['exiting', 'shutdown', 'stopping', 'stopped']
    startup_keywords = ['starting', 'startup', 'started']
    
    relevant_keywords = shutdown_keywords + startup_keywords
    
    lower_template = event_template.lower()

    # If the event template indicates a service start or stop, it's a potential
    # part of a restart event. The ProcessName is the key to link it with its
    # counterpart (shutdown or startup).
    if any(keyword in lower_template for keyword in relevant_keywords):
        return [f"PROCESSNAME_{process_name}"]
            
    return []