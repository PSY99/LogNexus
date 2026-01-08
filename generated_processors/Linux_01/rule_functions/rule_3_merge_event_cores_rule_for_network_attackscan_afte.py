from typing import Dict, List, Optional

def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
 """
 Identifies logs related to network attacks/scans based on specific templates
 and extracts the source IP or rhost as a linking key.
 """
 # Templates indicating a potential network attack or probe
 attack_templates = {
 'authentication failure',
 'check pass; user unknown',
 'connection unexpectedly closed',
 'peer died',
 'probable port-scan',
 'Connection from <*> on illegal port',
 'Kerberos authentication failed'
 }

 event_template = log.get('EventTemplate')

 # If the log's template does not match any of the attack templates, do nothing.
 if not event_template or event_template not in attack_templates:
 return []

 keys = []
 
 # Extract the source IP address if available.
 ip = log.get('ip')
 if ip:
 keys.append(f"IP_{ip}")

 # Extract the remote host FQDN(s) if available.
 rhosts = log.get('rhost')
 if rhosts and isinstance(rhosts, list):
 for host in rhosts:
 if host: # Ensure the host string is not empty
 keys.append(f"RHOST_{host}")

 return keys