from typing import Dict, List, Optional

def rule_6_merge_event_cores_rule_for_system_shutdown_identif(log: Dict) -> List[str]:
    """
    Identifies logs related to a system shutdown sequence.
    - Tags the trigger log ('shutting down for system reboot').
    - Tags subsequent related logs that indicate shutdown processes.
    """
    keys = []
    event_template = log.get('EventTemplate', '')

    if not event_template:
        return []

    # Rule Part 1: Identify the trigger for a 'System Shutdown' event.
    if event_template == 'shutting down for system reboot':
        # This log is the trigger that starts the shutdown event group.
        # The orchestrator will use this key to initiate a new event.
        keys.append('SYSTEM_SHUTDOWN_TRIGGER')
        # The trigger is also a member of the event group it starts.
        keys.append('SYSTEM_SHUTDOWN_MEMBER')
        return keys

    # Rule Part 2: Identify logs to be merged into an active 'System Shutdown' event.
    merge_keywords = [
        'shutdown succeeded',
        'terminating',
        'exiting',
        'received signal 15',
        '-TERM succeeded'
    ]

    if any(keyword in event_template for keyword in merge_keywords):
        # This log is a member of an ongoing shutdown event. The orchestrator
        # will merge it into the currently active 'System Shutdown' event.
        keys.append('SYSTEM_SHUTDOWN_MEMBER')

    return keys