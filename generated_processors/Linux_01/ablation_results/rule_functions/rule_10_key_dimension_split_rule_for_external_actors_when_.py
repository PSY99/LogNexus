from typing import Dict, List, Optional

def rule_10_key_dimension_split_rule_for_external_actors_when_(log: Dict) -> List[str]:
    """
    Extracts keys based on external source identifiers like 'rhost' or 'ip'.

    This rule is designed to create distinct logical events for actions
    originating from different external actors. By extracting the remote host
    or IP address as a key, the orchestrator can ensure that logs from
    different sources are not merged into the same event sequence.
    """
    keys = []

    # The rule uses 'rhost' as the primary example of a Key Source Identifier.
    # 'rhost' is expected to be a list of strings.
    rhosts = log.get('rhost')
    if isinstance(rhosts, list):
        for host in rhosts:
            if isinstance(host, str) and host:
                keys.append(f"RHOST_{host}")

    # The concept of an "external actor" also strongly applies to the 'ip' field.
    ip_address = log.get('ip')
    if isinstance(ip_address, str) and ip_address:
        keys.append(f"IP_{ip_address}")

    return keys