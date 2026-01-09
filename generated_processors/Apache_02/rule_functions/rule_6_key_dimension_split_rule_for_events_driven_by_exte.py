def rule_6_key_dimension_split_rule_for_events_driven_by_exte(log: Dict) -> List[str]:
    """
    [KEY DIMENSION SPLIT Rule] For events driven by external actors, if the
    Key Source Identifier (the `ip` field) changes between two log entries
    or 'Event Cores', they MUST be treated as belonging to new, separate
    logical events, even if they are temporally adjacent and share the same
    `EventTemplate`. Each unique `ip` value defines a distinct actor context.
    """
    ip_address = log.get('ip')
    event_template = log.get('EventTemplate')

    # This rule requires both an IP address (the actor identifier) and an
    # EventTemplate (the event context) to form a unique key.
    # If either is missing, the rule cannot be applied.
    if ip_address and event_template:
        # The composite key binds the actor's IP to the specific event template.
        # The orchestrator will group logs with this exact key. If a subsequent
        # log has the same template but a different IP, it will generate a
        # different key, effectively splitting the logical event as required.
        key = f"IP_TEMPLATE_{ip_address}_{event_template}"
        return [key]

    return []