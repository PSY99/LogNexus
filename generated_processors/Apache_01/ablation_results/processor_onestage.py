import ast
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Any

class EventProcessor:
 """
 Groups raw Apache HTTP Server logs into logical security events based on
 temporal proximity and correlation of identifiers like IP address and Process ID.
 """

 def __init__(self, logs: List[Dict[str, Any]]):
 """
 Initializes the EventProcessor with a list of log entries.

 Args:
 logs: A list of dictionaries, where each dictionary represents a log entry.
 """
 self.logs = logs
 self.processed_logs: List[Dict[str, Any]] = []

 # Pre-process logs to parse timestamps and other fields for efficient processing.
 for i, log in enumerate(self.logs):
 try:
 p_log = log.copy()
 p_log['original_index'] = i
 
 # Parse timestamp string into a datetime object.
 p_log['Timestamp'] = datetime.strptime(p_log['Timestamp'], '%Y-%m-%d %H:%M:%S')
 
 # Safely parse the 'Parameters' string into a list.
 if 'Parameters' in p_log and isinstance(p_log['Parameters'], str):
 p_log['Parameters'] = ast.literal_eval(p_log['Parameters'])
 elif 'Parameters' not in p_log:
 p_log['Parameters'] = []

 self.processed_logs.append(p_log)
 except (ValueError, SyntaxError, TypeError):
 # Skip logs that are malformed or have unparsable timestamps/parameters.
 # In a real-world scenario, these might be logged for review.
 continue
 
 # Sort logs chronologically to enable single-pass processing.
 self.processed_logs.sort(key=lambda x: x['Timestamp'])

 def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
 """
 Clusters the logs into logical security events using a single-pass algorithm.

 The method iterates through chronologically sorted logs, assigning each to an
 existing "active" event or creating a new one based on a set of heuristics.
 Events are considered "active" for a specific time window before being closed.

 Heuristics for merging a log into an event (in order of priority):
 1. IP Match: The log's IP address matches an IP associated with an active event.
 2. PID Match: The log's Process ID matches a PID associated with an active event.
 3. Repetitive Template Match: The log has the same event template as the last
 log in an active event (for grouping spam-like sequences).
 4. Interleaved Internal Log Match: An internal log (no IP) closely follows a
 log in an event that is associated with an IP address.
 5. Internal Sequence Match: An internal log (no IP/PID) follows another
 internal log, likely part of a system-level sequence like a restart.

 Returns:
 A tuple containing:
 - security_events (List[List[int]]): A list of events, where each event is
 a list of original log indices.
 - log_index_to_event_id (Dict[int, int]): A mapping from each log's
 original index to its assigned event ID.
 """
 # Maximum time gap to keep an event "active" for potential merging.
 # Set to 3 minutes to capture longer sequences like server restarts.
 MAX_TIME_GAP = timedelta(seconds=180)
 # Shorter time gap for tightly-coupled contextual matches.
 CONTEXT_GAP = timedelta(seconds=5)

 active_events: List[Dict[str, Any]] = []
 closed_events: List[Dict[str, Any]] = []

 for log in self.processed_logs:
 current_ts = log['Timestamp']
 original_index = log['original_index']

 # 1. Flush timed-out events from the active list to the closed list.
 still_active = []
 for event in active_events:
 if current_ts - event['last_timestamp'] > MAX_TIME_GAP:
 closed_events.append(event)
 else:
 still_active.append(event)
 active_events = still_active

 # 2. Find the best active event to merge the current log into.
 best_match_event = None
 
 # Iterate from most recently updated to least recent.
 for event in reversed(active_events):
 time_diff = current_ts - event['last_timestamp']

 # Heuristic 1: IP Match (strongest correlation for external activity)
 log_ip = log.get('ip')
 if log_ip and log_ip in event['ips']:
 best_match_event = event
 break

 # Heuristic 2: PID Match (strong correlation for process-specific activity)
 log_pid = log.get('PID')
 if log_pid and log_pid in event['pids']:
 best_match_event = event
 break
 
 # Heuristic 3: Repetitive Template Match (for sequential, identical logs)
 last_log_in_event = self.logs[event['log_indices'][-1]]
 if log.get('EventTemplate') and log.get('EventTemplate') == last_log_in_event.get('EventTemplate') and time_diff <= CONTEXT_GAP:
 best_match_event = event
 break

 # Heuristic 4: Interleaved Internal Log Match (internal log caused by external)
 if not log.get('ip') and event['ips'] and time_diff <= CONTEXT_GAP:
 best_match_event = event
 break

 # Heuristic 5: Internal Sequence Match (for system events like restarts)
 if not log.get('ip') and not log.get('PID') and not event['ips'] and not event['pids']:
 best_match_event = event
 break

 # 3. Merge log into the matched event or create a new one.
 if best_match_event:
 best_match_event['log_indices'].append(original_index)
 best_match_event['last_timestamp'] = current_ts
 if log.get('ip'):
 best_match_event['ips'].add(log.get('ip'))
 if log.get('PID'):
 best_match_event['pids'].add(log.get('PID'))
 
 # Move the updated event to the end to mark it as most recently used.
 active_events.remove(best_match_event)
 active_events.append(best_match_event)
 else:
 # No suitable active event found, create a new one.
 new_event = {
 'log_indices': [original_index],
 'last_timestamp': current_ts,
 'ips': {log.get('ip')} if log.get('ip') else set(),
 'pids': {log.get('PID')} if log.get('PID') else set(),
 }
 active_events.append(new_event)

 # 4. Finalize by closing all remaining active events.
 all_events = closed_events + active_events
 
 # Sort final events by the timestamp of their first log for deterministic output.
 all_events.sort(key=lambda e: self.logs[e['log_indices'][0]]['Timestamp'])

 security_events = [event['log_indices'] for event in all_events]
 
 # Create the log index to event ID mapping.
 log_index_to_event_id = {}
 for event_id, event_indices in enumerate(security_events):
 for log_index in event_indices:
 log_index_to_event_id[log_index] = event_id
 
 return security_events, log_index_to_event_id