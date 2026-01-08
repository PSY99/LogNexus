from typing import Dict, List, Optional

def rule_7_event_type_definition_rule_for_max_failures_an_eve(log: Dict) -> List[str]:
 """
 [EVENT TYPE DEFINITION Rule for Max Failures] An 'Event Core' containing the sequence of templates 'message repeated <*> times' (ID: 9), 'Disconnecting: Too many authentication failures' (ID: 10), and 'PAM <*> more authentication failures' (ID: 11) constitutes a complete, self-contained 'Max Authentication Failures Reached' event. This specific sequence represents the server's policy enforcement and should be identified as a distinct event type, which can then be part of a larger 'SSH Brute-Force Campaign'.
 """
 # Define the set of TemplateIDs that constitute the 'Max Authentication Failures Reached' event.
 max_failures_template_ids = {9, 10, 11}

 template_id = log.get('TemplateID')

 # Check if the log's TemplateID is one of the specified IDs.
 if template_id in max_failures_template_ids:
 # If it is, this log is part of the defined event.
 # We return a key that identifies this event type for the orchestrator.
 return ["EVENT_TYPE_Max_Authentication_Failures_Reached"]

 # If the log does not match the criteria, return an empty list.
 return []