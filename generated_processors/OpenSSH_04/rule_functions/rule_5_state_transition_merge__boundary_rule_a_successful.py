from typing import Dict, List, Optional

def rule_5_state_transition_merge__boundary_rule_a_successful(log: Dict) -> List[str]:
    """
    Extracts linking keys for SSH session lifecycle events based on TemplateID.

    - For 'session opened' (ID 18) and 'session closed' (ID 20), the linking key is the PID.
    - For 'disconnect' (ID 19) and 'session closed' (ID 20), the linking key is the remote host (rhost).
    This allows 'session closed' to link to both the preceding 'session opened' via PID and a
    nearly simultaneous 'disconnect' via rhost, even if the PIDs differ.
    """
    keys = []
    template_id = log.get('TemplateID')

    if not isinstance(template_id, int):
        return []

    # Rule applies to session open (18), disconnect (19), and session close (20)
    if template_id not in [18, 19, 20]:
        return []

    # Link 'session opened' (18) and 'session closed' (20) by the same PID
    if template_id in [18, 20]:
        pid = log.get('PID')
        if pid is not None:
            keys.append(f"PID_{pid}")

    # Link 'disconnect' (19) and 'session closed' (20) by the remote host IP
    if template_id in [19, 20]:
        rhosts = log.get('rhost')
        if isinstance(rhosts, list):
            for rhost_ip in rhosts:
                if rhost_ip:  # Ensure the IP string is not empty
                    keys.append(f"RHOST_{rhost_ip}")

    return keys