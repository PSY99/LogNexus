from typing import Dict, List

def rule_10_key_dimension_split_rule_when_applying_merging_rul(log: Dict) -> List[str]:
 """
 Extracts keys from 'ip' and 'rhost' fields to identify external actors.
 This allows the orchestrator to split event cores when the actor changes.
 """
 keys = []

 # Extract the IP address if it exists.
 ip_address = log.get('ip')
 if ip_address and isinstance(ip_address, str):
 keys.append(f"IP_{ip_address}")

 # Extract remote hosts from the 'rhost' list if it exists.
 remote_hosts = log.get('rhost')
 if remote_hosts and isinstance(remote_hosts, list):
 for host in remote_hosts:
 if host and isinstance(host, str):
 keys.append(f"RHOST_{host}")

 return keys