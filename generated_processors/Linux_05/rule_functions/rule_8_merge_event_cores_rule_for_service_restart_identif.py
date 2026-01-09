from typing import Dict, List, Optional

def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies service shutdown or startup events and extracts a linking key
    based on the process name.
    """
    # Keywords indicating a service shutdown or startup event core.
    # These are derived from the examples in the rule.
    shutdown_keywords = ['exiting', 'shutdown succeeded']
    startup_keywords = ['starting', 'startup succeeded']
    relevant_keywords = shutdown_keywords + startup_keywords

    # Safely retrieve the process name and log content.
    # Both are essential for this rule.
    process_name = log.get('ProcessName')
    log_content = log.get('LogContent')

    # If there's no process name or log content, we cannot create a linking key.
    if not process_name or not log_content:
        return []

    # Check if the log content contains any of the keywords indicating a
    # service state change (shutdown or startup).
    is_relevant_event = any(keyword in log_content for keyword in relevant_keywords)

    if is_relevant_event:
        # The ProcessName is the linking factor between a shutdown and a startup event.
        # The orchestrator will use this key to find a matching pair.
        return [f"PROCESSNAME_{process_name}"]

    # If the log does not match the criteria, return an empty list.
    return []