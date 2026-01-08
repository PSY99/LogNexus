from typing import Dict, List, Optional, Set


def rule_2_merge_event_cores_rule_for_ssh_bruteforce_after_in(log: Dict) -> List[str]:
    """
    Identifies authentication failure logs and extracts the source IP ('ip' or 'rhost')
    as a linking key for grouping into a single SSH Brute-Force Campaign.
    """
    # Rule condition: The log must be an authentication failure log.
    # These are identified by a specific set of TemplateIDs.
    auth_failure_template_ids = {1, 4, 7, 8}
    template_id = log.get('TemplateID')

    if template_id not in auth_failure_template_ids:
        return []

    # The linking key is the "Key Source Identifier", which can be in 'ip' or 'rhost'.
    # We use a set to collect unique identifiers to avoid duplicate keys.
    source_identifiers: Set[str] = set()

    # Extract from 'ip' field (Optional[str])
    ip_address: Optional[str] = log.get('ip')
    if ip_address:
        source_identifiers.add(ip_address)

    # Extract from 'rhost' field (List[str])
    remote_hosts: Optional[List[str]] = log.get('rhost')
    if remote_hosts:
        for host in remote_hosts:
            if host:  # Ensure the host string is not empty
                source_identifiers.add(host)

    # Format the collected identifiers into "KEYTYPE_keyvalue" strings.
    # The key type for an IP address or hostname is 'IP'.
    keys = [f"IP_{identifier}" for identifier in source_identifiers]

    return keys