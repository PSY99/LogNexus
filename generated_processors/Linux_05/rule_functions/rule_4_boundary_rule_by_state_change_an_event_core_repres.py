def rule_4_boundary_rule_by_state_change_an_event_core_repres(log: Dict) -> List[str]:
 """
 Identifies a successful login event which acts as a boundary for event correlation.

 This rule detects an 'Event Core' representing a successful login (e.g.,
 'session opened for user'). Such an event must not be merged with preceding
 'Network Attack' events. It signals the start of a new, distinct 'User Session'.
 """
 keys = []
 event_template = log.get('EventTemplate', '')

 if not event_template:
 return []

 # Keywords that indicate a successful login, which initiates a new user session boundary.
 success_login_patterns = [
 "session opened for user",
 "Accepted password for",
 "Accepted publickey for"
 ]

 # Check if the event template contains any of the success patterns.
 if any(pattern in event_template for pattern in success_login_patterns):
 # This key signals to the orchestrator that this log entry is a "state change"
 # and should start a new group, effectively creating a boundary.
 keys.append("STATECHANGE_BOUNDARY_SUCCESSFUL_LOGIN")

 return keys