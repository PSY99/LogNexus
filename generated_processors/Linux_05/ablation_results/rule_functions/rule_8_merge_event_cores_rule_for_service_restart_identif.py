from typing import Dict, List, Optional

def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies service shutdown or startup events and extracts a key based on the process name.
    This key allows the orchestrator to group related shutdown/startup events for a potential merge.
    """
    process_name = log.get('ProcessName')
    log_content = log.get('LogContent', '').lower()

    # A ProcessName is essential for linking shutdown and startup events.
    if not process_name:
        return []

    # Keywords to identify service state changes.
    # Based on rule examples: 'cupsd shutdown succeeded', 'ntpd exiting', 'cupsd startup succeeded'
    shutdown_keywords = ['shutdown', 'exiting', 'stopping', 'stopped']
    startup_keywords = ['startup', 'starting', 'started']

    is_shutdown_event = any(keyword in log_content for keyword in shutdown_keywords)
    is_startup_event = any(keyword in log_content for keyword in startup_keywords)

    # If the log represents either a shutdown or a startup event for a specific service,
    # return a key based on its process name. The orchestrator will use this key
    # to find the corresponding startup/shutdown event within the time window.
    if is_shutdown_event or is_startup_event:
        return [f"PROCESSNAME_{process_name}"]

    return []