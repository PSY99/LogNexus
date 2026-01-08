from typing import Dict, List, Optional

def rule_6_merge_event_cores_rule_for_system_shutdown_identif(log: Dict) -> List[str]:
    """
    Identifies logs related to a system shutdown sequence.

    This function flags logs that are either triggers for a system shutdown
    (like specific service termination events) or are part of the shutdown
    process (containing keywords like 'terminating' or 'exiting'). It returns
    a constant key 'EVENT_SystemShutdown' for all such logs, allowing an
    orchestrator to group them into a single logical event.

    Args:
        log: A dictionary representing a single log entry.

    Returns:
        A list containing the key 'EVENT_SystemShutdown' if the log is
        identified as part of a shutdown sequence, otherwise an empty list.
    """
    template_id = log.get('TemplateID')
    event_template = log.get('EventTemplate', '')

    # Trigger TemplateIDs that initiate a "System Shutdown" event
    trigger_template_ids = {233, 228}

    # Conditions for logs that should be merged into the shutdown event
    mergeable_template_ids = {198}
    mergeable_keywords = ['terminating', 'exiting']

    # Check if the log is a trigger for the shutdown event
    if template_id in trigger_template_ids:
        return ['EVENT_SystemShutdown']

    # Check if the log is a mergeable event core
    if template_id in mergeable_template_ids:
        return ['EVENT_SystemShutdown']

    # Check for keywords in the event template for broader matching
    if any(keyword in event_template for keyword in mergeable_keywords):
        return ['EVENT_SystemShutdown']

    return []