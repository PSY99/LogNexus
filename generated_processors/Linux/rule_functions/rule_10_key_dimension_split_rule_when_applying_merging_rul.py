def rule_10_key_dimension_split_rule_when_applying_merging_rul(log: Dict) -> List[str]:
 keys = []
 ip = log.get('ip', None)
 rhost_list = log.get('rhost', [])
 
 # Extract IP-based key if available
 if ip:
 keys.append(f"IP_{ip}")
 
 # Extract each rhost as a separate key
 for rhost in rhost_list:
 if rhost:
 keys.append(f"IP_{rhost}")
 
 # If both IP and rhost are present, create a composite key to represent distinct external actors
 if ip and rhost_list:
 for rhost in rhost_list:
 if rhost:
 keys.append(f"IP_IP_{ip}_{rhost}")
 
 return keys