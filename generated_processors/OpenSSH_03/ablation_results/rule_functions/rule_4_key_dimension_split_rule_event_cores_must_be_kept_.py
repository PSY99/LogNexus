def rule_4_key_dimension_split_rule_event_cores_must_be_kept_(log: Dict) -> List[str]:
 """
 [KEY DIMENSION SPLIT Rule] 'Event Cores' MUST be kept in separate logical events
 if their associated Key Source Identifier (the value in the 'ip' or 'rhost' field)
 is different. This is a hard boundary ensuring that simultaneous activities
 from different actors are not incorrectly merged.
 """
 keys = []
 
 # Extract the 'ip' field if it's a non-empty string
 ip_address = log.get('ip')
 if ip_address and isinstance(ip_address, str):
 keys.append(f"IP_{ip_address}")
 
 # Extract from the 'rhost' field, which is expected to be a list of strings
 remote_hosts = log.get('rhost')
 if remote_hosts and isinstance(remote_hosts, list):
 for host in remote_hosts:
 if host and isinstance(host, str):
 keys.append(f"RHOST_{host}")
 
 return keys