from typing import Dict, List

def rule_5_merge_event_cores_rule_for_mass_shutdown_notificat(log: Dict) -> List[str]:
    """
    Identifies logs with the specific EventTemplate 'mod_jk2 Shutting down'
    and extracts a key based on this template to enable grouping of consecutive occurrences.
    """
    target_template = 'mod_jk2 Shutting down'
    
    # Safely get the EventTemplate from the log
    event_template = log.get('EventTemplate')
    
    # Check if the log's template matches the target template
    if event_template == target_template:
        # The key is the template itself, allowing the orchestrator to group
        # all consecutive logs that share this exact key.
        return [f"TEMPLATE_{event_template}"]
        
    return []