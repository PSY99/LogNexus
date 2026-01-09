from typing import Dict, List, Optional

def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
    """
    Extracts IP or rhost as a key if the log matches specific network failure/connection template IDs.
    """
    # Template IDs for failure or connection events like 'authentication failure',
    # 'check pass; user unknown', 'connection from', or 'Authentication failed from'.
    target_template_ids = {197, 195, 196, 205}
    
    keys = []
    
    # Check if the log's TemplateID matches one of the specified network attack/scan templates.
    if log.get('TemplateID') in target_template_ids:
        # The rule states to merge based on the Key Source Identifier (IP or rhost).
        
        # Extract IP address if available.
        ip_address = log.get('ip')
        if ip_address:
            keys.append(f"IP_{ip_address}")
            
        # Extract rhost FQDNs if available. The 'rhost' field is a list.
        remote_hosts = log.get('rhost', [])
        if remote_hosts:
            for host in remote_hosts:
                if host:  # Ensure the host string is not empty
                    keys.append(f"RHOST_{host}")
                    
    return keys