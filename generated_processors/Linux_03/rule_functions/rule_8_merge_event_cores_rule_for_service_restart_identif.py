def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies service shutdown or startup events and extracts the process name as a key.
    """
    process_name = log.get('ProcessName')
    log_content = log.get('LogContent', '')

    # A ProcessName is essential for linking shutdown and startup events for the same service.
    if not process_name:
        return []

    # Keywords derived from the rule's examples: "named: exiting", "cupsd shutdown succeeded",
    # "starting BIND", "cupsd startup succeeded". These indicate a service state change.
    relevant_keywords = [
        "exiting",
        "shutdown succeeded",
        "starting",
        "startup succeeded"
    ]

    lower_log_content = log_content.lower()

    # If the log content contains any of the keywords, it's a relevant event core.
    # The orchestrator will handle the logic of matching a shutdown with a startup.
    # This function's only job is to flag the log as potentially relevant with a linking key.
    if any(keyword in lower_log_content for keyword in relevant_keywords):
        # The linking key is based on the process name, as specified by the rule.
        return [f"PROCESSNAME_{process_name}"]

    return []