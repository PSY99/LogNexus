def rule_7_key_dimension_split_rule_event_cores_must_not_be_m(log: dict) -> list:
 keys = set()

 # Extract the source IP from the 'ip' field (Optional[str])
 ip_address = log.get('ip')
 if ip_address and isinstance(ip_address, str):
 keys.add(f"IP_{ip_address}")

 # Extract source IP(s) from the 'rhost' field (List[str])
 remote_hosts = log.get('rhost')
 if remote_hosts and isinstance(remote_hosts, list):
 for host in remote_hosts:
 if host and isinstance(host, str):
 keys.add(f"IP_{host}")

 return list(keys)