from typing import Dict, List, Optional

def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
    """
    Extracts a linking key based on the source host ('rhost') for specific
    network attack/scan related TemplateIDs.

    Rule: "[MERGE EVENT CORES Rule for Network Attack/Scan] After initial PID-based
    grouping, identify all 'Event Cores' containing failure templates like
    'authentication failure' (TemplateID 197), 'check pass; user unknown'
    (TemplateID 195), 'Kerberos authentication failed' (TemplateID 204), or
    'ttloop: peer died' (TemplateID 209). Merge all such cores, regardless of
    their original PID or process name, if they share the exact same Key Source
    Identifier (IP address or FQDN from the 'rhost' field) and occur within a
    15-minute sliding window. Additionally, merge high-frequency 'ftpd:
    connection from' (TemplateID 196) events from the same source into this
    group. This reconstructs a single logical 'Network Attack' event from a
    single actor."
    """
    keys = []
    
    # These are the TemplateIDs identified in the rule as relevant for network attacks.
    target_template_ids = {195, 196, 197, 204, 209}
    
    template_id = log.get('TemplateID')
    
    # Check if the log event is one of the specified types.
    if template_id in target_template_ids:
        # The rule specifies linking by the 'rhost' field (IP or FQDN).
        remote_hosts = log.get('rhost')
        
        # 'rhost' is a list, so we iterate through it.
        if remote_hosts and isinstance(remote_hosts, list):
            for host in remote_hosts:
                # Ensure the host value is a non-empty string before creating a key.
                if isinstance(host, str) and host:
                    keys.append(f"RHOST_{host}")
                    
    return keys