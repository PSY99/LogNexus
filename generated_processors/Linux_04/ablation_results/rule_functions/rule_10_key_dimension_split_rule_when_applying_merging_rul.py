from typing import Dict, List


def rule_10_key_dimension_split_rule_when_applying_merging_rul(log: Dict) -> List[str]:
    """
    Extracts keys from 'ip' and 'rhost' fields to prevent merging events
    from different external actors.
    """
    keys = []

    # Extract IP address if present
    ip_address = log.get('ip')
    if ip_address and isinstance(ip_address, str) and ip_address.strip():
        keys.append(f"IP_{ip_address.strip()}")

    # Extract remote hosts if present. 'rhost' is expected to be a list.
    remote_hosts = log.get('rhost')
    if remote_hosts and isinstance(remote_hosts, list):
        for host in remote_hosts:
            if host and isinstance(host, str) and host.strip():
                keys.append(f"RHOST_{host.strip()}")

    return keys