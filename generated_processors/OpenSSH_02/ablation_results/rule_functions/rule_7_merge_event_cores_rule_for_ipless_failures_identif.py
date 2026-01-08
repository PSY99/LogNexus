def rule_7_merge_event_cores_rule_for_ipless_failures_identif(log: Dict) -> List[str]:
    if log.get('rhost') or log.get('ip'):
        return []

    process_name = log.get('ProcessName')
    event_template = log.get('EventTemplate')

    if not process_name or not event_template:
        return []

    failure_keywords = [
        'fail', 'failure', 'unknown', 'disconnecting', 'denied', 'invalid',
        'error', 'refused', 'check pass'
    ]
    template_lower = event_template.lower()
    if not any(keyword in template_lower for keyword in failure_keywords):
        return []

    key = f"PROCESSNAME_EVENTTEMPLATE_{process_name}_{event_template}"
    return [key]