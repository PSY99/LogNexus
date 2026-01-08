def rule_5_merge_event_cores_rule_for_mass_shutdown_notificat(log: dict) -> list[str]:
 """
 Identifies logs with the specific EventTemplate 'mod_jk2 Shutting down'
 and creates a linking key based on this template.
 """
 event_template = log.get('EventTemplate')

 if event_template == 'mod_jk2 Shutting down':
 # The rule states that logs with this exact template should be merged.
 # Therefore, the template itself serves as the perfect linking key.
 # The orchestrator will use this key, along with its own time-window logic,
 # to group consecutive occurrences.
 return [f"TEMPLATE_{event_template}"]

 return []