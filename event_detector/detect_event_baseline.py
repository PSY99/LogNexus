import re
from datetime import datetime, timedelta
from collections import defaultdict, deque

# --- Heuristic Session Building Rules ---
def detect_security_events_Linux(merged_data):
 # ... (This function's code remains unchanged, omitted here for brevity)
 SESSION_TIME_WINDOW = timedelta(minutes=10)
 ENTITY_TIME_WINDOW = timedelta(seconds=30)
 PARAM_TIME_WINDOW = timedelta(seconds=60)
 WEAK_SESSION_TIME_WINDOW = timedelta(minutes=2)
 num_logs = len(merged_data)
 if num_logs == 0: return [], {}
 parent = list(range(num_logs)); size = [1] * num_logs
 def find(i):
 if parent[i] == i: return i
 parent[i] = find(parent[i]); return parent[i]
 def union(i, j):
 root_i, root_j = find(i), find(j)
 if root_i != root_j:
 if size[root_i] < size[root_j]: root_i, root_j = root_j, root_i
 parent[root_j] = root_i; size[root_i] += size[root_j]
 PARAM_BLACKLIST = {'root', 'test', 'admin', 'user', 'guest', 'nobody', 'unknown', '0', '1', '(uid=0)', 'NODEVssh', 'N/A', ''}
 def get_entity(log_content):
 match = re.search(r'combo\s+([^:[]+)', log_content)
 return match.group(1).strip() if match else None
 last_log_by_pid, last_log_by_ip_template, last_log_by_entity, last_log_by_param, last_log_by_na_template = {}, {}, {}, {}, {}
 for log_idx, log_entry in enumerate(merged_data):
 timestamp, pid, ip, template, params, entity = log_entry.get('Timestamp'), log_entry.get('PID'), log_entry.get('ip', 'N/A'), log_entry.get('EventTemplate', ''), log_entry.get('Parameters', []), get_entity(log_entry['LogContent'])
 if not isinstance(timestamp, datetime): continue
 try:
 if pid and int(pid) > 0:
 if pid in last_log_by_pid and (timestamp - last_log_by_pid[pid]['timestamp']) <= SESSION_TIME_WINDOW: union(log_idx, last_log_by_pid[pid]['log_idx'])
 last_log_by_pid[pid] = {'log_idx': log_idx, 'timestamp': timestamp}
 except (ValueError, TypeError): pass
 if ip != 'N/A':
 key = (ip, template)
 if key in last_log_by_ip_template and (timestamp - last_log_by_ip_template[key]['timestamp']) <= SESSION_TIME_WINDOW: union(log_idx, last_log_by_ip_template[key]['log_idx'])
 last_log_by_ip_template[key] = {'log_idx': log_idx, 'timestamp': timestamp}
 if entity:
 if entity in last_log_by_entity and (timestamp - last_log_by_entity[entity]['timestamp']) <= ENTITY_TIME_WINDOW: union(log_idx, last_log_by_entity[entity]['log_idx'])
 last_log_by_entity[entity] = {'log_idx': log_idx, 'timestamp': timestamp}
 for param in params:
 if param and param not in PARAM_BLACKLIST:
 if param in last_log_by_param and (timestamp - last_log_by_param[param]['timestamp']) <= PARAM_TIME_WINDOW: union(log_idx, last_log_by_param[param]['log_idx'])
 last_log_by_param[param] = {'log_idx': log_idx, 'timestamp': timestamp}
 if ip == 'N/A':
 if template in last_log_by_na_template and (timestamp - last_log_by_na_template[template]['timestamp']) <= WEAK_SESSION_TIME_WINDOW: union(log_idx, last_log_by_na_template[template]['log_idx'])
 last_log_by_na_template[template] = {'log_idx': log_idx, 'timestamp': timestamp}
 events = defaultdict(list)
 for i in range(num_logs): events[find(i)].append(i)
 security_events = list(events.values())
 log_index_to_event_id = {log_idx: event_id for event_id, logs in enumerate(security_events) for log_idx in logs}
 return security_events, log_index_to_event_id

def detect_security_events_openssh(merged_data):
 """
 Groups log entries into security events based on semantic similarity of log content and temporal proximity.
 
 :param merged_data: List of log dictionaries. Each log has the following fields:
 - 'Timestamp': datetime object (not string)
 - 'PID': str or int
 - 'ip': str (could be "N/A")
 - 'LogContent': str, the raw log message
 - 'EventTemplate': str, the template with parameters removed
 - 'Parameters': list[str], values extracted from the log that match the template
 :return: Tuple of (security_events, log_index_to_event_id)
 - security_events: List of lists. Each inner list contains indices of logs in the same event.
 - log_index_to_event_id: Dict mapping log index to its assigned event ID.
 """
 # The maximum time difference (in seconds) between two consecutive logs
 # for them to be considered part of the same security event. A session-based
 # timeout helps group related activities that occur closely in time.
 SESSION_TIMEOUT = 120 # 2 minutes

 # This list will store the final groups of log indices. Each inner list
 # represents a distinct security event.
 security_events = []
 
 # This dictionary provides a fast lookup from a log's index in the input data
 # to the ID of the event it has been assigned to. The event ID corresponds
 # to the index in the `security_events` list.
 log_index_to_event_id = {}

 # This list holds the state of currently "active" events. An event is
 # considered active if its most recent log entry occurred within the
 # SESSION_TIMEOUT window. Keeping track of active events allows for efficient
 # correlation of incoming logs without re-scanning all past events.
 # Each state is a dictionary containing:
 # - 'event_id': The index of the event in the `security_events` list.
 # - 'last_timestamp': The timestamp of the last log added to this event.
 # - 'pids': A set of all Process IDs encountered in this event.
 # - 'ips': A set of all source IP addresses (excluding "N/A") in this event.
 active_events_state = []

 # Process each log entry sequentially. The algorithm assumes that the
 # `merged_data` is sorted chronologically by timestamp.
 for i, log in enumerate(merged_data):
 current_timestamp = log['Timestamp']
 current_pid = log['PID']
 current_ip = log['ip']

 # Prune events from the active state that have timed out. This is a crucial
 # optimization step. An event is considered timed out if the time gap
 # between the current log and the last recorded log of that event exceeds
 # the SESSION_TIMEOUT. This prevents merging unrelated logs that are far
 # apart in time and keeps the `active_events_state` list manageable.
 active_events_state = [
 s for s in active_events_state
 if (current_timestamp - s['last_timestamp']).total_seconds() <= SESSION_TIMEOUT
 ]

 found_event_for_log = False
 
 # To determine if the current log belongs to an existing active event,
 # we iterate through the active events. We check in reverse order to
 # prioritize more recent events, as a log is most likely to be related
 # to the latest activity.
 for event_state in reversed(active_events_state):
 # A log is considered part of an existing event if it shares a
 # common Process ID (PID) or a source IP address. This heuristic
 # effectively correlates activities, such as a brute-force attack
 # from a single IP that spawns multiple processes, or a sequence of
 # actions performed by a single process.
 is_related = (
 current_pid in event_state['pids'] or
 (current_ip != "N/A" and current_ip in event_state['ips'])
 )

 if is_related:
 # The log is related to this event. Assign it and update the event's state.
 event_id = event_state['event_id']
 security_events[event_id].append(i)
 log_index_to_event_id[i] = event_id

 # Update the event's state with the current log's information to
 # reflect the latest activity and context.
 event_state['last_timestamp'] = current_timestamp
 event_state['pids'].add(current_pid)
 if current_ip != "N/A":
 event_state['ips'].add(current_ip)
 
 found_event_for_log = True
 # Once a suitable event is found, we break the loop and move to the next log entry.
 break

 # If the current log does not match any of the active events, it signifies
 # the beginning of a new potential security event.
 if not found_event_for_log:
 new_event_id = len(security_events)
 security_events.append([i])
 log_index_to_event_id[i] = new_event_id

 # Create a new state tracker for this new event and add it to the
 # list of active events.
 new_event_state = {
 'event_id': new_event_id,
 'last_timestamp': current_timestamp,
 'pids': {current_pid},
 'ips': {current_ip} if current_ip != "N/A" else set()
 }
 active_events_state.append(new_event_state)

 return security_events, log_index_to_event_id

def detect_security_events_apache(merged_data):
 """
 Groups log entries into security events based on sliding window and similarity criteria.
 
 This function uses a graph-based approach to cluster logs. Each log is a node,
 and an edge exists between two nodes if they are within a specific time window
 and share a common attribute (like PID or IP address). The function finds
 the connected components in this graph, with each component representing a
 security event. A Breadth-First Search (BFS) algorithm is used to traverse
 the graph and identify these components efficiently.

 :param merged_data: List of log dictionaries, assumed to be sorted by Timestamp.
 Each log has the following fields:
 - 'Timestamp': datetime object (not string)
 - 'PID': str
 - 'ip': str (could be "N/A")
 :return: Tuple of (security_events, log_index_to_event_id)
 - security_events: List of lists. Each inner list contains indices of logs in the same event.
 - log_index_to_event_id: Dict mapping log index to its assigned event ID.
 """
 # Get the total number of log entries.
 n = len(merged_data)
 
 # A dictionary to keep track of which event each log index belongs to.
 # This also serves as a 'visited' set for our graph traversal.
 log_index_to_event_id = {}
 
 # The final list of security events, where each event is a list of log indices.
 security_events = []
 
 # Define the time window for considering logs as part of the same event.
 # This can be tuned based on the expected nature of security events.
 # For example, a 60-second window means logs must occur within 60 seconds
 # of a related log to be grouped together.
 time_window = timedelta(seconds=60)
 
 # Iterate through each log entry to find potential new security events.
 for i in range(n):
 # If this log has already been assigned to an event, we can skip it.
 if i in log_index_to_event_id:
 continue
 
 # This log starts a new security event.
 # The event ID is simply the current number of events found.
 event_id = len(security_events)
 
 # Use a queue for a Breadth-First Search (BFS) to find all related logs (connected component).
 queue = deque([i])
 # This list will store all log indices for the current event being built.
 current_event_indices = []
 
 # Mark the starting log as part of the new event.
 log_index_to_event_id[i] = event_id
 
 # Process the queue until all logs in the current event component are found.
 while queue:
 # Get the next log from the queue to process its neighbors.
 current_idx = queue.popleft()
 current_event_indices.append(current_idx)
 current_log = merged_data[current_idx]
 
 # Look for related logs that occur after the current log.
 # We don't need to look backwards because the outer loop ensures
 # any previous related logs would have already been processed and grouped.
 for j in range(current_idx + 1, n):
 candidate_log = merged_data[j]
 
 # Optimization: Since logs are sorted by timestamp, if the current
 # candidate is outside the time window of the log we are expanding from,
 # all subsequent logs will also be outside the window. We can stop searching.
 if candidate_log['Timestamp'] - current_log['Timestamp'] > time_window:
 break
 
 # If the candidate log has already been assigned to an event, skip it.
 if j in log_index_to_event_id:
 continue
 
 # Define the similarity criteria for grouping logs into an event.
 is_similar = False
 
 # Criterion 1: Same Process ID (PID).
 # We ignore "N/A" PIDs as they are not specific enough for correlation.
 if current_log['PID'] != "N/A" and current_log['PID'] == candidate_log['PID']:
 is_similar = True
 
 # Criterion 2: Same source IP address.
 # We ignore "N/A" IPs for the same reason.
 elif current_log['ip'] != "N/A" and current_log['ip'] == candidate_log['ip']:
 is_similar = True
 
 # If the candidate log is similar and within the time window,
 # it belongs to the current security event.
 if is_similar:
 # Assign the candidate to the current event.
 log_index_to_event_id[j] = event_id
 # Add the candidate to the queue to find its neighbors in subsequent iterations.
 queue.append(j)

 # After the BFS is complete for this component, add the list of indices
 # to the main security_events list.
 # Sorting the indices provides a consistent and predictable output format.
 current_event_indices.sort()
 security_events.append(current_event_indices)
 
 return security_events, log_index_to_event_id