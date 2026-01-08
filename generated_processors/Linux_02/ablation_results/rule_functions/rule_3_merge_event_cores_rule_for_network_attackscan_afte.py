def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
 """
 After initial PID-based grouping, identify all 'Event Cores' containing failure templates like 'authentication failure', 'check pass; user unknown', or 'connection from'. Merge all such cores, regardless of their original PID or process name (e.g., sshd, ftpd), if they share the exact same Key Source Identifier (IP address or rhost FQDN) and occur within a 15-minute sliding window. This reconstructs a single logical 'Network Attack' or 'Connection Flood' event from a single external actor.
 """
 keys = []
 event_template = log.get('EventTemplate')

 if not event_template:
 return []

 # Define the trigger phrases for network attack/scan events
 trigger_phrases = [
 'authentication failure',
 'check pass; user unknown',
 'connection from'
 ]

 # Check if the event template indicates a potential network attack
 template_lower = event_template.lower()
 is_relevant_template = any(phrase in template_lower for phrase in trigger_phrases)

 if is_relevant_template:
 # If the template matches, extract the Key Source Identifier (IP or rhost)
 ip_address = log.get('ip')
 if ip_address:
 keys.append(f"IP_{ip_address}")

 rhosts = log.get('rhost')
 if rhosts and isinstance(rhosts, list):
 for rhost in rhosts:
 if rhost: # Ensure the rhost value is not empty
 keys.append(f"RHOST_{rhost}")

 return keys