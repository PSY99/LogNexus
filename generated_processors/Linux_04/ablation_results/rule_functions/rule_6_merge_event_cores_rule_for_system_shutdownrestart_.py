def rule_6_merge_event_cores_rule_for_system_shutdownrestart_(log: Dict) -> List[str]:
    """
    Identifies system shutdown/restart related events and extracts a linking key based on ProcessName.
    """
    keys = []
    
    # TemplateIDs related to the shutdown/restart sequence as per the rule.
    # 229: 'shutting down'
    # 227: 'received signal 15: Terminated'
    # 198: '<*> shutdown succeeded'
    shutdown_template_ids = {229, 227, 198}
    
    template_id = log.get('TemplateID')
    
    if template_id in shutdown_template_ids:
        process_name = log.get('ProcessName')
        
        # A valid ProcessName is required to link the events in the sequence.
        if process_name:
            # This key allows the orchestrator to group the start ('shutting down') 
            # and end ('shutdown succeeded') events for the same process.
            key = f"SHUTDOWN_RESTART_PROCESSNAME_{process_name}"
            keys.append(key)
            
    return keys