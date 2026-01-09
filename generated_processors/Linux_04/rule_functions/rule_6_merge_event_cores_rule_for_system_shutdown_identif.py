from typing import Dict, List, Optional

def rule_6_merge_event_cores_rule_for_system_shutdown_identif(log: Dict) -> List[str]:
    """
    Identifies logs related to a system shutdown event.

    This rule looks for a specific trigger log ('shutting down for system reboot')
    and several related logs that indicate shutdown processes (containing keywords
    like 'shutdown succeeded', 'terminating', 'exiting', 'received signal 15').
    All these logs are tagged with a common 'SYSTEM_SHUTDOWN' key to allow an
    orchestrator to group them into a single event.
    """
    event_template = log.get('EventTemplate', '')
    if not event_template:
        return []

    # The trigger for the system shutdown event
    trigger_template = 'shutting down for system reboot'

    # Keywords found in logs that should be merged into the shutdown event
    merge_keywords = [
        'shutdown succeeded',
        'terminating',
        'exiting',
        'received signal 15'
    ]

    # Check if the log is the trigger
    if event_template == trigger_template:
        return ['SYSTEM_SHUTDOWN']

    # Check if the log is a mergeable event core
    for keyword in merge_keywords:
        if keyword in event_template:
            return ['SYSTEM_SHUTDOWN']

    return []