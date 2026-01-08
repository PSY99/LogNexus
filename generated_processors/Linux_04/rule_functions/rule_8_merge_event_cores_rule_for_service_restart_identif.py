from typing import Dict, List, Optional

def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies service startup or shutdown events and extracts the process name as a key.
    This allows the orchestrator to link a shutdown event with a subsequent startup
    event from the same process to form a single "Service Restart" event.
    """
    # Keywords indicating a service is starting or stopping.
    # These are derived from the rule's examples and common service log messages.
    startup_keywords = ['starting', 'started', 'initializing', 'listening for']
    shutdown_keywords = ['exiting', 'stopping', 'shutting down', 'terminated', 'closing']

    # Safely get the necessary fields from the log dictionary.
    process_name: Optional[str] = log.get('ProcessName')
    event_template: str = log.get('EventTemplate', '').lower()  # Use lower for case-insensitive matching

    # A process name is essential for linking startup and shutdown events.
    if not process_name:
        return []

    # Check if the event template indicates a startup or shutdown.
    is_startup = any(keyword in event_template for keyword in startup_keywords)
    is_shutdown = any(keyword in event_template for keyword in shutdown_keywords)

    # If the log represents either a startup or a shutdown event for a known process,
    # create a key based on the process name. The orchestrator will use this key
    # to find matching pairs within the specified time window.
    if is_startup or is_shutdown:
        return [f"PROCESSNAME_{process_name}"]

    # If the log is not a relevant startup or shutdown event, return an empty list.
    return []