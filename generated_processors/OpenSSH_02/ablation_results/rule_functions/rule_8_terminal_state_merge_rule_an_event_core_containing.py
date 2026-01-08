def rule_8_terminal_state_merge_rule_an_event_core_containing(log: Dict) -> List[str]:
    """
    Extracts linking keys from terminal connection logs.

    This rule identifies logs that signify the end of a connection attempt
    (e.g., 'Received disconnect', 'Connection closed'). If such a log is found,
    it extracts the source 'ip' or 'rhost' as a linking key. This allows
    the orchestrator to merge this terminal event with a preceding failure
    event from the same source.
    """
    keys = []

    # Define the set of event templates that indicate a terminal connection state.
    terminal_templates = {
        "Received disconnect from <*>",
        "Connection closed by <*>",
        "fatal: Write failed: Connection reset by peer"
    }

    event_template = log.get('EventTemplate')

    # Check if the log's template matches one of the terminal state templates.
    if event_template in terminal_templates:
        # If it's a terminal log, extract the source identifier ('ip' or 'rhost').

        # Extract IP address if present.
        ip_address = log.get('ip')
        if ip_address:
            keys.append(f"IP_{ip_address}")

        # Extract remote hosts ('rhost') if present. 'rhost' is a list.
        rhosts = log.get('rhost')
        if isinstance(rhosts, list):
            for rhost in rhosts:
                if rhost:  # Ensure the value is not an empty string
                    keys.append(f"RHOST_{rhost}")

    return keys