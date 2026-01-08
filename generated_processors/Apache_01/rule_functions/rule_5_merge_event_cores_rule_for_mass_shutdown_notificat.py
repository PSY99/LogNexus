from typing import Dict, List

def rule_5_merge_event_cores_rule_for_mass_shutdown_notificat(log: Dict) -> List[str]:
 """
 Identifies logs with the specific EventTemplate 'mod_jk2 Shutting down'
 and creates a linking key based on that template.
 """
 # The rule is specific to one event template.
 target_template = 'mod_jk2 Shutting down'

 # Safely retrieve the EventTemplate from the log entry.
 event_template = log.get('EventTemplate')

 # If the log's template matches the target, create a key.
 # This key allows the orchestrator to group all such consecutive events.
 if event_template == target_template:
 # The key is based on the template itself to group identical events.
 return [f"TEMPLATE_{target_template}"]

 # If the rule condition is not met, return an empty list.
 return []