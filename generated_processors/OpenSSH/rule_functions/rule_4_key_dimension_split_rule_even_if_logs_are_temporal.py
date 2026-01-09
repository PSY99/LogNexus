from typing import Dict, List, Optional

def rule_4_key_dimension_split_rule_even_if_logs_are_temporal(log: Dict) -> List[str]:
    """
    Extracts keys from 'ip' or 'rhost' fields to identify distinct external actors.
    This forces a split in event cores when the source IP/host changes, as each
    unique source identifier represents a distinct actor and context.
    """
    keys = []

    # The rule identifies 'ip' as a Key Source Identifier for external interactions.
    ip_address = log.get('ip')
    if ip_address and isinstance(ip_address, str):
        keys.append(f"IP_{ip_address}")

    # The rule also identifies 'rhost' as a Key Source Identifier.
    # The 'rhost' field is specified as a list of strings.
    remote_hosts = log.get('rhost')
    if remote_hosts and isinstance(remote_hosts, list):
        for host in remote_hosts:
            # Ensure the item in the list is a valid string before creating a key.
            if host and isinstance(host, str):
                keys.append(f"RHOST_{host}")

    return keys