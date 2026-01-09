def rule_4_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies logs that are part of a service restart sequence.

    This rule looks for a specific trigger event template ('Graceful restart requested, doing restart')
    or subsequent configuration/startup logs that lack a client IP address. All such logs
    are tagged with a common key to allow the orchestrator to group them into a single
    'Service Restart' event.
    """
    event_template = log.get('EventTemplate', '')
    ip_address = log.get('ip')

    # The specific template that triggers the start of a service restart sequence.
    trigger_template = 'Graceful restart requested, doing restart'

    # Prefixes of templates for subsequent logs that are part of the restart.
    # These are only considered if they lack a client IP.
    subsequent_template_prefixes = [
        'suEXEC mechanism enabled',
        'LDAP:',
        'mod_python:',
        'mod_security/'
    ]

    # Condition 1: The log is the specific trigger for the restart.
    if event_template == trigger_template:
        return ['EVENT_SERVICE_RESTART']

    # Condition 2: The log is a subsequent configuration/startup message
    # AND it lacks a client IP address.
    if ip_address is None:
        for prefix in subsequent_template_prefixes:
            if event_template.startswith(prefix):
                return ['EVENT_SERVICE_RESTART']

    # If the log matches neither condition, it's not part of this event.
    return []