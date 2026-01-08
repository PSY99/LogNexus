from typing import Dict, List

def rule_10_key_dimension_split_rule_when_applying_merging_rul(log: Dict) -> List[str]:
 """
 Extracts 'rhost' values as linking keys to ensure events from distinct
 external actors are not merged.
 """
 keys = []
 rhosts = log.get('rhost')

 # The 'rhost' field is expected to be a list of strings.
 if rhosts and isinstance(rhosts, list):
 for host in rhosts:
 # Ensure the host value is a non-empty string before creating a key.
 if isinstance(host, str) and host:
 keys.append(f"RHOST_{host}")

 return keys