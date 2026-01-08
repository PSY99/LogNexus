from typing import Dict, List, Optional

def rule_4_merge_event_cores_rule_for_user_enumeration_identi(log: Dict) -> List[str]:
 """
 Identifies logs related to SSH user enumeration attempts and extracts the source IP
 address as a linking key.

 This rule targets logs with specific TemplateIDs (1, 2, 3) which correspond to
 'Invalid user', 'input_userauth_request: invalid user', and 'pam_unix: user unknown'.
 The linking key is the source IP address, found in either the 'ip' or 'rhost' fields.
 """
 # The rule applies only to logs with specific TemplateIDs.
 relevant_template_ids = {1, 2, 3}
 if log.get('TemplateID') not in relevant_template_ids:
 return []

 keys = set()
 
 # The linking key is the source IP, which can be in 'ip' or 'rhost'.
 
 # Extract from 'ip' field
 ip_address = log.get('ip')
 if ip_address and isinstance(ip_address, str):
 keys.add(f"IP_{ip_address}")
 
 # Extract from 'rhost' field, which is a list
 remote_hosts = log.get('rhost')
 if remote_hosts and isinstance(remote_hosts, list):
 for host in remote_hosts:
 if host and isinstance(host, str):
 keys.add(f"IP_{host}")

 return list(keys)