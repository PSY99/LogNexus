def rule_4_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies logs that are part of a service restart sequence by checking for
    specific start, middle, and end event patterns.
    """
    event_template = log.get('EventTemplate')
    log_content = log.get('LogContent', '')

    # Define the start and end markers for the service restart sequence based on EventTemplate.
    start_template = 'Graceful restart requested, doing restart'
    end_template = 'Apache/<*> configured -- resuming normal operations'

    # Define prefixes for the intermediate logs based on LogContent.
    # These are logs that occur between the start and end of a service restart.
    middle_prefixes = (
        'Digest:',
        'LDAP:',
        'mod_python:',
        'mod_security/'
    )

    # A single, static key is used to tag all logs belonging to this sequence.
    # The orchestrator will use this key to group the start, middle, and end logs.
    service_restart_key = 'EVENT_SERVICE_RESTART'

    # Check if the log matches the start or end conditions.
    if event_template in (start_template, end_template):
        return [service_restart_key]

    # Check if the log matches one of the middle conditions.
    # Using strip() to handle potential leading whitespace in LogContent.
    if log_content.strip().startswith(middle_prefixes):
        return [service_restart_key]

    # If none of the conditions are met, this log is not part of a service restart sequence.
    return []