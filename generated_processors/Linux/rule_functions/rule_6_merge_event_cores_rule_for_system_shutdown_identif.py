def rule_6_merge_event_cores_rule_for_system_shutdown_identif(log: Dict) -> List[str]:
 event_template = log.get('EventTemplate', '').strip()
 parameters = log.get('Parameters', [])
 keys = []

 # Check for trigger events
 if event_template in ['shutting down for system reboot', 'Switching to runlevel: 6']:
 keys.append("EVENT_TRIGGER_System_Shutdown")

 # Check for event cores (mergeable logs)
 core_triggers = [
 'shutdown succeeded',
 'terminating',
 'exiting',
 'received signal 15',
 'un-registering and exiting',
 'klogd shutdown succeeded',
 'Kernel logging (proc) stopped',
 'Kernel log daemon terminating'
 ]
 
 if any(core in event_template for core in core_triggers):
 keys.append("EVENT_CORE_System_Shutdown")

 # Extract non-blacklisted parameters as linking keys
 blacklisted_words = {'root', 'admin', 'system', 'user', 'unknown', 'local'}
 for param in parameters:
 if param and param not in blacklisted_words:
 keys.append(f"PARAM_{param}")

 return keys