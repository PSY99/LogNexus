def rule_6_key_dimension_split_rule_for_events_driven_by_exte(log: Dict) -> List[str]:
 """
 Extracts a composite key from the IP address and EventTemplate to split event
 streams by the source actor (IP).
 """
 ip_address = log.get('ip')
 event_template = log.get('EventTemplate')

 # The rule applies only when both an IP (the external actor identifier) and
 # an EventTemplate (the event type) are present in the log.
 if ip_address and event_template:
 # The composite key uniquely identifies an event stream for a specific
 # actor (IP) performing a specific action (EventTemplate). This allows
 # the orchestrator to treat events with the same template but different
 # source IPs as separate logical events.
 key = f"IP_TEMPLATE_{ip_address}_{event_template}"
 return [key]

 # If the log does not have an IP or an EventTemplate, this rule does not apply.
 return []