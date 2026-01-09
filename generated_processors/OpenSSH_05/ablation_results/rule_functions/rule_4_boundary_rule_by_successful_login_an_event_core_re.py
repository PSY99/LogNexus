from typing import Dict, List, Optional


def rule_4_boundary_rule_by_successful_login_an_event_core_re(log: Dict) -> List[str]:
    """
    Identifies a successful login event and creates a special 'BOUNDARY' key.

    This key signals to the orchestrator that a new, distinct session has begun,
    and it should not be merged with any preceding events (like SSH attacks)
    that share the same source identifier (IP address).
    """
    keys: List[str] = []
    template: Optional[str] = log.get('EventTemplate')

    if not template:
        return []

    # Successful login events are identified by specific templates.
    # Using 'startswith' for "Accepted" covers various auth methods (password, publickey, etc.).
    # Using 'in' for "session opened" covers PAM messages.
    is_success_login = (
        template.startswith('Accepted') or
        'session opened for user' in template
    )

    if is_success_login:
        # This log marks a boundary. We create a special key using the source identifier (IP).
        # The orchestrator will use this key to prevent merging with prior attack sessions
        # that share the same IP.

        # Collect all potential source IP addresses from the log.
        source_ips = set()
        ip = log.get('ip')
        if ip and isinstance(ip, str):
            source_ips.add(ip)

        rhosts = log.get('rhost')
        if rhosts and isinstance(rhosts, list):
            for rhost in rhosts:
                if rhost and isinstance(rhost, str):
                    source_ips.add(rhost)

        # For each unique IP, create a boundary key.
        for ip_addr in source_ips:
            # The key format "BOUNDARY_IP_{ip_addr}" is a composite key that signals
            # a boundary condition tied to a specific IP.
            keys.append(f"BOUNDARY_IP_{ip_addr}")

    return keys