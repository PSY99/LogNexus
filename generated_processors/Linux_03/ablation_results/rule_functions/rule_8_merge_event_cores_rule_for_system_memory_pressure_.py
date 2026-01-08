from typing import Dict, List, Optional

def rule_8_merge_event_cores_rule_for_system_memory_pressure_(log: Dict) -> List[str]:
    """
    Extracts a static key if the log matches the 'Out of Memory' template.
    """
    # The rule targets a specific event template for grouping.
    target_template = 'Out of Memory: Killed process <*>'
    
    # Safely get the EventTemplate from the log
    event_template = log.get('EventTemplate')
    
    # If the log's template matches the target, return a static key.
    # This key will be the same for all logs matching this template,
    # allowing the orchestrator to group them as a single system-wide event.
    if event_template == target_template:
        return ['OOM_SYSTEM_PRESSURE']
        
    # If the template does not match, no key is generated.
    return []