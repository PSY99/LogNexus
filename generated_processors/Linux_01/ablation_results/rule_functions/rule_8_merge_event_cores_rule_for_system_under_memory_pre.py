from typing import Dict, List, Optional

def rule_8_merge_event_cores_rule_for_system_under_memory_pre(log: Dict) -> List[str]:
 """
 Identifies 'Out of Memory' events and provides a common key for grouping.

 This rule targets logs with TemplateID 254, which corresponds to the template
 'Out of Memory: Killed process <*> (<*>)'. The goal is to merge all such
 events within a time window into a single 'System Under Memory Pressure' event.
 This function provides a static key to enable that grouping by the orchestrator.

 Args:
 log: A dictionary representing a single log entry.

 Returns:
 A list containing the static key 'EVENT_SystemUnderMemoryPressure' if the
 log matches the OOM template, otherwise an empty list.
 """
 # The rule specifies merging all events with TemplateID 254.
 # To achieve this, we provide a single, static key for all matching logs.
 # The orchestrator will use this key to group them together.
 if log.get('TemplateID') == 254:
 return ['EVENT_SystemUnderMemoryPressure']
 
 return []