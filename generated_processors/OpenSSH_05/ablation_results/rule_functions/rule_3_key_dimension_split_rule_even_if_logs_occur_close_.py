from typing import Dict, List


def rule_3_key_dimension_split_rule_even_if_logs_occur_close_(log: Dict) -> List[str]:
    """
    Extracts Key Source Identifiers like Source IP or 'rhost' to enforce event separation.
    Each unique identifier represents a distinct actor and must start a new event context.
    """
    keys = []

    # Extract Source IP from the 'ip' field
    source_ip = log.get('ip')
    if source_ip and isinstance(source_ip, str) and source_ip.strip():
        keys.append(f"IP_{source_ip.strip()}")

    # Extract remote hosts from the 'rhost' field, which is a list
    remote_hosts = log.get('rhost')
    if remote_hosts and isinstance(remote_hosts, list):
        for host in remote_hosts:
            if host and isinstance(host, str) and host.strip():
                keys.append(f"RHOST_{host.strip()}")

    return keys