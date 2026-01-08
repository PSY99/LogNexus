from typing import Dict, List

def rule_5_merge_event_cores_rule_for_mass_shutdown_notificat(log: Dict) -> List[str]:
 """
 [MERGE EVENT CORES Rule for Mass Shutdown Notifications]
 Identify a log with EventTemplate: 'mod_jk2 Shutting down'.
 This key allows merging all subsequent, consecutive logs that share this
 exact same EventTemplate.
 """
 # The rule is specific to one event template.
 target_template = 'mod_jk2 Shutting down'

 # Check if the log's EventTemplate matches the target.
 if log.get('EventTemplate') == target_template:
 # Create a key based on the template itself. This allows the orchestrator
 # to group all logs that produce this same key.
 return [f"TEMPLATE_{target_template}"]

 # If the log's template does not match, no key is generated.
 return []