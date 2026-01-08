def rule_4_merge_event_cores_rule_for_service_restart_identif(log: dict) -> list[str]:
 """
 Identifies logs related to a service restart sequence based on EventTemplates.

 This rule flags three types of logs with a common key:
 1. Trigger logs indicating module configuration.
 2. Intermediate logs indicating service initialization, if they lack an IP.
 3. A specific boundary log indicating the service has resumed normal operations.

 All matching logs are tagged with 'SERVICE_RESTART_GLOBAL' to be grouped
 by a stateful orchestrator.
 """
 event_template = log.get('EventTemplate')
 if not event_template:
 return []

 # Define the templates for each part of the service restart sequence.
 trigger_templates = {
 'mod_security/<*> configured',
 'LDAP: Built with OpenLDAP LDAP SDK'
 }
 intermediate_templates = {
 'workerEnv.init() ok <*>',
 'mod_jk child init <*> <*>'
 }
 boundary_template = 'Apache/<*> configured -- resuming normal operations'

 # 1. Check for trigger logs.
 if event_template in trigger_templates:
 return ['SERVICE_RESTART_GLOBAL']

 # 2. Check for intermediate logs, which have an additional condition.
 if event_template in intermediate_templates:
 # Condition: must lack an 'ip' field.
 if not log.get('ip'):
 return ['SERVICE_RESTART_GLOBAL']

 # 3. Check for the boundary log.
 if event_template == boundary_template:
 return ['SERVICE_RESTART_GLOBAL']

 # If the log matches none of the above, it's not part of this sequence.
 return []