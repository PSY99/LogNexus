from typing import Dict, List, Optional

def rule_10_contextual_enrichment_rule_dns_mismatch_logs_with_(log: Dict) -> List[str]:
    """
    Extracts the PID as a linking key for specific DNS mismatch logs.

    This rule identifies logs related to DNS reverse mapping failures (TemplateID 0 or 25).
    These logs are considered contextual enrichment for other events. The function extracts
    the Process ID (PID) to link this enrichment data to the core connection event
    that shares the same PID.

    Args:
        log: A dictionary representing a single log entry.

    Returns:
        A list containing the formatted PID key (e.g., ["PID_12345"]) if the log
        matches the specified TemplateIDs and has a PID, otherwise an empty list.
    """
    keys = []
    template_id = log.get('TemplateID')

    if template_id in [0, 25]:
        pid: Optional[int] = log.get('PID')
        if pid is not None:
            keys.append(f"PID_{pid}")

    return keys