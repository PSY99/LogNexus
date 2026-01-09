from typing import Dict, List, Optional

def rule_10_key_dimension_split_rule_when_applying_merging_rul(log: Dict) -> List[str]:
    """
    [KEY DIMENSION SPLIT Rule] When applying merging rules based on Key Source Identifiers (e.g., 'rhost'),
    if the identifier's value changes (e.g., from IP '1.2.3.4' to '5.6.7.8'), a new logical event must be started.
    'Event Cores' from distinct external actors must never be merged into the same event.
    """
    keys = []

    # Extract keys from 'rhost' which is a list of remote hosts/IPs
    rhost_list = log.get('rhost')
    if isinstance(rhost_list, list):
        for host in rhost_list:
            if isinstance(host, str) and host:
                keys.append(f"RHOST_{host}")

    # Extract key from 'ip' which is a single source IP
    ip_addr = log.get('ip')
    if isinstance(ip_addr, str) and ip_addr:
        keys.append(f"IP_{ip_addr}")

    return keys