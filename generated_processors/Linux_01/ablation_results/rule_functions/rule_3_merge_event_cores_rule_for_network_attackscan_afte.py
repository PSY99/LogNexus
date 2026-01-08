from typing import Dict, List, Optional

def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
 """
 [MERGE EVENT CORES Rule for Network Attack/Scan]
 Extracts the remote host (rhost) as a key if the log's TemplateID
 matches known network attack/scan patterns.
 """
 # TemplateIDs for 'authentication failure', 'check pass; user unknown',
 # 'connection from', or 'Connection from <*> on illegal port'.
 target_template_ids = {197, 195, 196, 249}
 
 keys = []
 
 # Check if the log's TemplateID is one of the specified ones.
 if log.get('TemplateID') in target_template_ids:
 # The rule states to merge based on the Key Source Identifier,
 # which is the IP address or FQDN from the 'rhost' field.
 rhosts = log.get('rhost')
 
 # Ensure 'rhost' is a non-empty list before processing.
 if isinstance(rhosts, list):
 for host in rhosts:
 if host: # Ensure the host string is not empty
 keys.append(f"RHOST_{host}")
 
 return keys