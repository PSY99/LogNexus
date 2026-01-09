def rule_2_merge_event_cores_rule_for_ssh_bruteforcecredentia(log: Dict) -> List[str]:
    """
    Extracts the source IP as a linking key for sshd authentication failures.
    This enables grouping of brute-force attempts from the same actor across
    different server processes.
    """
    # Rule applies only to the 'sshd' process
    if log.get('ProcessName') != 'sshd':
        return []

    # Identify common sshd authentication failure templates
    event_template = log.get('EventTemplate', '')
    failure_signatures = [
        'Failed password for',
        'Invalid user',
        'pam_unix(sshd:auth): authentication failure'
    ]

    is_auth_failure = any(sig in event_template for sig in failure_signatures)

    if not is_auth_failure:
        return []

    # Extract the source IP (Key Source Identifier) from 'ip' or 'rhost' fields
    source_ips = set()
    
    # The 'ip' field is typically a single string
    ip_from_ip_field = log.get('ip')
    if ip_from_ip_field and isinstance(ip_from_ip_field, str):
        source_ips.add(ip_from_ip_field)

    # The 'rhost' field is typically a list of strings
    rhosts = log.get('rhost')
    if rhosts and isinstance(rhosts, list):
        for rhost_ip in rhosts:
            if rhost_ip and isinstance(rhost_ip, str):
                source_ips.add(rhost_ip)

    # Format the found IPs into the required KEYTYPE_keyvalue format
    keys = [f"IP_{ip}" for ip in source_ips]

    return keys