from typing import Dict, List, Set, Optional

def rule_3_merge_event_cores_rule_for_scanning_activity_ident(log: Dict) -> List[str]:
 """
 Identifies potential SSH scanning/probing activity based on specific TemplateIDs
 and extracts the source IP ('ip' or 'rhost') as a linking key.
 """
 # TemplateIDs indicating pre-authentication errors or protocol anomalies
 TARGET_TEMPLATE_IDS: Set[int] = {5, 13, 14, 16, 21, 22, 23, 24, 26}
 
 keys: List[str] = []
 template_id: Optional[int] = log.get('TemplateID')

 # Check if the log's TemplateID matches the rule's criteria
 if template_id in TARGET_TEMPLATE_IDS:
 # Use a set to store unique IP addresses/hosts to avoid duplicate keys from the same log
 source_identifiers = set()

 # Extract from 'ip' field
 ip_address: Optional[str] = log.get('ip')
 if ip_address:
 source_identifiers.add(ip_address)

 # Extract from 'rhost' field, which is a list
 remote_hosts: Optional[List[str]] = log.get('rhost')
 if isinstance(remote_hosts, list):
 for host in remote_hosts:
 if host: # Ensure the host string is not empty
 source_identifiers.add(host)
 
 # Format the collected identifiers into the required key format
 for identifier in source_identifiers:
 keys.append(f"IP_{identifier}")
 
 return keys