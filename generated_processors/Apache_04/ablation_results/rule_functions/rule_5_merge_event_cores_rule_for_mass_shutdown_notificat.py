from typing import Dict, List

def rule_5_merge_event_cores_rule_for_mass_shutdown_notificat(log: Dict) -> List[str]:
 """
 Identifies a log with EventTemplate: 'mod_jk2 Shutting down' and creates a
 linking key based on this exact template.
 """
 # The rule is specific to this exact EventTemplate.
 target_template = 'mod_jk2 Shutting down'

 # Safely get the EventTemplate from the log.
 event_template = log.get('EventTemplate')

 # If the log's template matches the target, create a key from it.
 # This key allows the orchestrator to group all consecutive logs
 # that share this template.
 if event_template == target_template:
 return [f"TEMPLATE_{target_template}"]

 # If the log does not match the rule, return no keys.
 return []