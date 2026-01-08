from typing import Dict, List, Optional

def rule_3_boundary_rule_by_successful_login_an_event_core_in(log: Dict) -> List[str]:
 """
 [BOUNDARY Rule by Successful Login] An 'Event Core' initiated by a log with
 EventTemplate ID 18 ('pam_unix(sshd:session): session opened for user...')
 represents a successful login. This core MUST start a new, distinct
 'Successful SSH Session' event. It must NOT be merged with any preceding
 'SSH Attack Campaign' event, even if the Key Source Identifier is identical.
 All subsequent logs sharing the same PID as the 'session opened' log are
 part of this new session event.
 """
 # This rule triggers on a specific event: a successful session opening.
 # The key that links all subsequent events in this new session is the PID.
 if log.get('TemplateID') == 18:
 pid = log.get('PID')
 if pid is not None:
 # This PID marks the start of a new, distinct successful session.
 # The orchestrator will use this key to group subsequent logs.
 return [f"PID_{pid}"]
 
 return []