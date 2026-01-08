from typing import Dict, List, Optional

def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
 """
 [MERGE EVENT CORES Rule for Network Attack/Scan] After initial PID-based grouping,
 identify all 'Event Cores' containing failure templates like 'authentication failure',
 'connection unexpectedly closed', 'peer died', 'probable port-scan', or
 'Connection from <*> on illegal port'. Merge all such cores, regardless of their
 original PID or process name, if they share the exact same Key Source Identifier
 (IP address or rhost FQDN).
 """
 
 failure_keywords = [
 'authentication failure',
 'connection unexpectedly closed',
 'peer died',
 'probable port-scan',
 'Connection from <*> on illegal port'
 ]

 event_template = log.get('EventTemplate', '')
 
 # Check if the log's template matches any of the specified failure types.
 is_failure_event = any(keyword in event_template for keyword in failure_keywords)

 if not is_failure_event:
 return []

 keys = []
 
 # Extract the Key Source Identifier (IP address or rhost FQDN).
 # The orchestrator will use these keys to merge events from the same source.
 
 ip_address = log.get('ip')
 if ip_address:
 keys.append(f"IP_{ip_address}")

 rhosts = log.get('rhost')
 if rhosts and isinstance(rhosts, list):
 for host in rhosts:
 if host: # Ensure the host string is not empty
 keys.append(f"RHOST_{host}")
 
 return keys