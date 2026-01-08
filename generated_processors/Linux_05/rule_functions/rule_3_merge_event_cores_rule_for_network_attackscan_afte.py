from typing import Dict, List, Optional

def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
 """
 After initial PID-based grouping, identify all 'Event Cores' containing
 failure templates like 'authentication failure', 'check pass; user unknown',
 'FAILED LOGIN', 'connection unexpectedly closed', 'peer died',
 'probable port-scan', or 'Connection from <*> on illegal port'.
 Merge all such cores, regardless of their original PID or process name,
 if they share the exact same Key Source Identifier (IP address or rhost FQDN).
 """
 
 # Define the set of phrases that indicate a potential network attack/scan
 attack_phrases = {
 'authentication failure',
 'check pass; user unknown',
 'failed login',
 'connection unexpectedly closed',
 'peer died',
 'probable port-scan',
 'connection from <*> on illegal port'
 }

 event_template = log.get('EventTemplate', '')
 if not event_template:
 return []

 template_lower = event_template.lower()

 # Check if the event template matches any of the attack phrases
 is_attack_event = any(phrase in template_lower for phrase in attack_phrases)

 if not is_attack_event:
 return []

 # If it's an attack event, extract keys from the source identifier (IP or rhost)
 keys = []
 
 # Extract IP address if it exists
 ip_address = log.get('ip')
 if ip_address:
 keys.append(f"IP_{ip_address}")

 # Extract remote host(s) if they exist
 remote_hosts = log.get('rhost')
 if remote_hosts:
 for host in remote_hosts:
 if host: # Ensure the host string is not empty
 keys.append(f"RHOST_{host}")

 return keys