def rule_4_boundary_rule_by_state_change__success_an_event_co(log: dict) -> list[str]:
 """
 Identifies successful SSH authentication logs to create a hard boundary,
 starting a new, distinct 'Successful SSH Session' event.
 """
 # Templates indicating a successful SSH login.
 success_templates = {
 'Accepted password for <*> from <*> port <*> ssh2',
 'pam_unix(sshd:session): session opened for user <*>'
 }

 event_template = log.get('EventTemplate')
 if not event_template or event_template not in success_templates:
 return []

 keys = []
 parameters = log.get('Parameters', [])
 user = None
 ip = None

 if event_template == 'Accepted password for <*> from <*> port <*> ssh2':
 # Expected parameters: [user, ip, port]
 if len(parameters) >= 2:
 user = parameters[0]
 ip = parameters[1]

 elif event_template == 'pam_unix(sshd:session): session opened for user <*>':
 # Expected parameters: [user]
 if len(parameters) >= 1:
 user = parameters[0]
 
 # IP is not in parameters for this template; get it from the log's root level.
 ip = log.get('ip')
 if not ip:
 rhost = log.get('rhost')
 if rhost and isinstance(rhost, list) and len(rhost) > 0:
 ip = rhost[0]

 # If a user and IP were successfully extracted, create a specific session key.
 # This key acts as a boundary, preventing merges with preceding events (like
 # brute-force attempts) that might only share an IP.
 if user and ip and isinstance(user, str) and isinstance(ip, str):
 keys.append(f"SUCCESSFUL_SSH_SESSION_{user}_{ip}")

 return keys