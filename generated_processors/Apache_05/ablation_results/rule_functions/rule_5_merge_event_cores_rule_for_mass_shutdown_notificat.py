from typing import Dict, List

def rule_5_merge_event_cores_rule_for_mass_shutdown_notificat(log: Dict) -> List[str]:
    """
    Identifies logs with the specific EventTemplate 'mod_jk2 Shutting down'
    to enable merging of consecutive shutdown notifications.
    """
    target_template = 'mod_jk2 Shutting down'
    
    if log.get('EventTemplate') == target_template:
        # The key for linking these logs is the template itself. The orchestrator
        # will use this key to group consecutive logs that appear close in time.
        return [f"TEMPLATE_{target_template}"]
        
    return []