from typing import Dict, List, Optional

def rule_8_merge_event_cores_rule_for_service_restart_identif(log: Dict) -> List[str]:
    """
    Identifies service shutdown or startup events and extracts the process name as a key.
    This key allows the orchestrator to group potential restart events for the same service.
    """
    keys = []
    
    # The ProcessName is the primary linking entity for a service.
    process_name: Optional[str] = log.get('ProcessName')
    if not process_name:
        return []

    # The rule targets logs indicating a service state change (shutdown or startup).
    # We check the template for a more reliable match than raw content.
    event_template: str = log.get('EventTemplate', '').lower()
    
    # Check for keywords that signify a service state change.
    is_shutdown = 'shutdown' in event_template
    is_startup = 'startup' in event_template

    # If the log is either a shutdown or startup event for a known process,
    # create a key based on the process name. The orchestrator will use this
    # key to find pairs of shutdown/startup events.
    if is_shutdown or is_startup:
        key = f"PROCESSNAME_{process_name}"
        keys.append(key)
        
    return keys