def rule_3_merge_event_cores_rule_for_complete_ssh_session_id(log: dict) -> list[str]:
 """
 Extracts a composite key of (User, Source IP) for SSH session events.

 This rule identifies the start ('Accepted password', 'session opened') and
 end ('session closed') of an SSH session. The linking key is a combination
 of the user and the source IP address, allowing these events to be merged
 into a complete session. Events like 'Received disconnect' are relevant but
 often lack explicit user information in the log entry, so they cannot
 produce this specific composite key on their own.
 """
 import re

 log_content = log.get('LogContent', '')
 is_relevant_log = (
 'Accepted password for' in log_content or
 'session opened for user' in log_content or
 'session closed for user' in log_content
 # 'Received disconnect from' is also relevant, but often lacks a user
 # so it's handled implicitly by the user extraction logic.
 )

 if not is_relevant_log:
 return []

 user = None
 source_ip = None
 parameters = log.get('Parameters', [])
 template = log.get('EventTemplate', '')

 # --- Extract User ---
 # For 'Accepted password', 'session opened', and 'session closed' events,
 # the user is typically the first parameter. We avoid templates like
 # 'Received disconnect from' where the first parameter is an IP.
 if parameters and 'user' in template:
 # A simple heuristic: the first parameter is the user.
 potential_user = parameters[0]
 # Ensure it's not something that looks like an IP address.
 if not re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', potential_user):
 user = potential_user

 # --- Extract Source IP ---
 # 1. Prioritize dedicated IP fields from the log structure.
 source_ip = log.get('ip')
 if not source_ip:
 rhost = log.get('rhost')
 if rhost and isinstance(rhost, list) and len(rhost) > 0:
 source_ip = rhost[0]

 # 2. Fallback: If no dedicated IP field, scan parameters for an IP address.
 if not source_ip and parameters:
 for param in parameters:
 if isinstance(param, str) and re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', param):
 source_ip = param
 break

 # --- Construct Key ---
 # The rule requires both User and Source IP to form a linking key.
 if user and source_ip:
 return [f"USER_IP_{user}_{source_ip}"]

 return []