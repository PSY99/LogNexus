from typing import Dict, List, Optional

def rule_1_group_all_logs_sharing_the_exact_same_process_id_p(log: Dict) -> List[str]:
    """
    Extracts a linking key based on the Process ID (PID).

    This rule groups all logs that share the exact same PID. The presence of a
    PID is considered a strong indicator for creating a foundational 'Event Core'.
    If a log entry contains a PID, a key in the format "PID_<pid_value>" is
    generated. If no PID is present, no key is generated.
    """
    pid = log.get('PID')

    if pid is not None:
        # The rule is absolute and foundational, so a single key is sufficient.
        return [f"PID_{pid}"]

    # If no PID is found in the log entry, return an empty list.
    return []