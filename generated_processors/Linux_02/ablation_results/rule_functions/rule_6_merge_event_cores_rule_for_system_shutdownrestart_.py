from typing import Dict, List, Optional

def rule_6_merge_event_cores_rule_for_system_shutdownrestart_(log: Dict) -> List[str]:
    """
    Identifies logs related to a system shutdown sequence.
    """
    keys = []
    event_template = log.get('EventTemplate')

    if isinstance(event_template, str):
        # Keywords that indicate a log is part of a shutdown sequence.
        # This covers the trigger ('<*> shutdown succeeded') and the subsequent
        # logs to be merged ('terminating', 'exiting').
        shutdown_keywords = ['shutdown succeeded', 'terminating', 'exiting']

        if any(keyword in event_template for keyword in shutdown_keywords):
            # This single, constant key flags the log as part of a system shutdown event.
            # The main orchestrator will use this key to group all related logs
            # until a 'System Boot' trigger (identified by a different rule) is found.
            keys.append("SYSTEM_SHUTDOWN_SEQUENCE")

    return keys