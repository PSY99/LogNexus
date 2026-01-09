from typing import Dict, List

def rule_5_merge_event_cores_rule_for_mass_shutdown_notificat(log: Dict) -> List[str]:
    """
    Identifies logs with the specific EventTemplate 'mod_jk2 Shutting down'
    to enable grouping of consecutive shutdown notifications.
    """
    event_template = log.get('EventTemplate')
    
    if event_template == 'mod_jk2 Shutting down':
        # The key is the template itself, as all logs to be merged share this exact template.
        # The orchestrator will handle the "consecutive" and "time window" logic.
        return ['TEMPLATE_mod_jk2 Shutting down']
        
    return []