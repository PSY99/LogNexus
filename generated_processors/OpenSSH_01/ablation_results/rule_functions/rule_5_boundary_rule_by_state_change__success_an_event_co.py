def rule_5_boundary_rule_by_state_change__success_an_event_co(log: Dict) -> List[str]:
 """
 [BOUNDARY Rule by State Change - Success] An 'Event Core' representing a successful login
 (e.g., containing logs with templates like 'Accepted password for <user> from <ip>' or
 'session opened for user <user>') acts as a hard boundary. Do NOT merge this success
 core with any preceding 'SSH Brute-Force/Scanning' event, even from the same source IP.
 The successful login starts a new, distinct 'Successful SSH Session' event.
 """
 keys = []
 event_template = log.get('EventTemplate')

 if not event_template:
 return []

 # Define substrings that indicate a successful SSH login based on the rule's examples.
 success_indicators = [
 'Accepted password for',
 'session opened for user'
 ]

 is_success_event = any(indicator in event_template for indicator in success_indicators)

 if is_success_event:
 # A successful login creates a boundary. This key signals to the orchestrator
 # to start a new event group and not merge with previous ones from the same IP.

 # Prioritize the 'ip' field for the source address.
 ip_address = log.get('ip')

 # Fallback to 'rhost' if 'ip' is not available.
 if not ip_address:
 rhosts = log.get('rhost')
 if isinstance(rhosts, list) and rhosts:
 ip_address = rhosts[0]

 if ip_address:
 # Create a specific boundary key tied to the source IP.
 # Format: BOUNDARY_SUCCESS_IP_<ip_address>
 keys.append(f"BOUNDARY_SUCCESS_IP_{ip_address}")

 return keys