import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

class EventProcessor:
 """
 Groups raw Apache log entries into logical security events based on
 temporal proximity and correlation of identifiers like IP, PID, and EventTemplate.
 """

 def __init__(self, logs: List[Dict]):
 """
 Initializes the EventProcessor with a list of log entries.

 Args:
 logs: A list of dictionaries, where each dictionary represents a log entry.
 """
 processed_logs = []
 if not isinstance(logs, list):
 self.logs = []
 return

 for i, log in enumerate(logs):
 # Create a copy to avoid modifying the original input list
 new_log = log.copy()
 new_log['original_index'] = i

 # Parse timestamp string into a datetime object, handling potential errors
 try:
 ts_str = new_log.get('Timestamp')
 if ts_str:
 new_log['Timestamp'] = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
 else:
 # Assign a default old timestamp if missing to ensure stable sorting
 new_log['Timestamp'] = datetime.min
 except (ValueError, TypeError):
 new_log['Timestamp'] = datetime.min

 # Ensure PID is consistently typed as an integer or None
 pid_val = new_log.get('PID')
 if pid_val:
 try:
 new_log['PID'] = int(pid_val)
 except (ValueError, TypeError):
 new_log['PID'] = None
 
 # Ensure TemplateID is a string for consistent keying
 if 'TemplateID' in new_log:
 new_log['TemplateID'] = str(new_log.get('TemplateID'))

 processed_logs.append(new_log)

 # Sort logs chronologically to enable efficient sliding-window processing
 processed_logs.sort(key=lambda x: x['Timestamp'])
 self.logs = processed_logs

 def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
 """
 Clusters logs into logical events using a single-pass algorithm with a
 sliding time window and a Union-Find data structure.

 The logic correlates logs based on:
 1. Shared client IP address within a time window (session activity).
 2. Shared Process ID (PID) within a time window (process context).
 3. Membership in known system-level event sequences (e.g., restarts).
 4. Heuristic linking of external (IP-based) and internal (system) logs
 that are immediately adjacent in time, suggesting a causal link.

 Returns:
 A tuple containing:
 - security_events: A list of lists, where each inner list contains the
 original indices of logs belonging to one event.
 - log_index_to_event_id: A dictionary mapping each log's original index
 to its assigned event ID.
 """
 if not self.logs:
 return [], {}

 n = len(self.logs)

 # --- Union-Find (Disjoint Set Union) Implementation ---
 # Implemented with path compression and union by size for efficiency.
 # This structure is ideal for incrementally merging groups of logs.
 parent = list(range(n))
 size = [1] * n

 def find(i: int) -> int:
 """Finds the root of the set containing element i with path compression."""
 if parent[i] == i:
 return i
 parent[i] = find(parent[i])
 return parent[i]

 def union(i: int, j: int):
 """Merges the sets containing elements i and j using union by size."""
 root_i = find(i)
 root_j = find(j)
 if root_i != root_j:
 # Merge smaller tree into larger tree
 if size[root_i] < size[root_j]:
 root_i, root_j = root_j, root_i
 parent[root_j] = root_i
 size[root_i] += size[root_j]
 # --- End of Union-Find Implementation ---

 # --- Correlation Parameters and Domain Knowledge ---
 # A wider window for session-like activities (e.g., from the same IP).
 SESSION_WINDOW = timedelta(seconds=10)
 # A very tight window for linking causally related but distinct log types.
 CAUSAL_WINDOW = timedelta(seconds=2)

 # Template ID sets for specific, known system event sequences.
 # These are based on typical Apache module behavior.
 RESTART_IDS = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '18'}
 JK_INIT_IDS = {'10', '11', '12', '15', '20'}
 SHUTDOWN_ID = '17'

 # --- Main Clustering Loop ---
 # Iterate through each log and compare it with previous logs within the sliding window.
 for i in range(n):
 log_i = self.logs[i]
 ts_i = log_i['Timestamp']
 ip_i = log_i.get('ip')
 pid_i = log_i.get('PID')
 id_i = log_i.get('TemplateID')

 # Look backwards in the time window.
 for j in range(i - 1, -1, -1):
 log_j = self.logs[j]
 ts_j = log_j['Timestamp']

 # Stop if we've moved beyond the session window.
 if ts_i - ts_j > SESSION_WINDOW:
 break

 # Skip if logs are already in the same event group.
 if find(i) == find(j):
 continue

 ip_j = log_j.get('ip')
 pid_j = log_j.get('PID')
 id_j = log_j.get('TemplateID')

 # --- Correlation Rules ---

 # Rule 1: Strong correlation by shared IP (external user activity).
 if ip_i and ip_i == ip_j:
 union(i, j)
 continue

 # Rule 2: Strong correlation by shared PID (internal process activity).
 if pid_i and pid_i == pid_j:
 union(i, j)
 continue

 # Rule 3: Correlation of known system-level sequences.
 # These are often IP-less and have varying PIDs.
 if id_i == SHUTDOWN_ID and id_j == SHUTDOWN_ID:
 union(i, j)
 continue
 if id_i in RESTART_IDS and id_j in RESTART_IDS:
 union(i, j)
 continue
 if id_i in JK_INIT_IDS and id_j in JK_INIT_IDS:
 union(i, j)
 continue

 # Rule 4: Heuristic correlation for interleaved events.
 # Links external activity (IP) to immediate internal responses (no IP).
 # This is crucial for attributing system errors to specific requests.
 is_interleaved = (ip_i and not ip_j) or (not ip_i and ip_j)
 if is_interleaved and (ts_i - ts_j < CAUSAL_WINDOW):
 union(i, j)
 continue

 # --- Format the output as per the contract ---
 # Group log indices by their final root in the DSU structure.
 event_groups = {}
 for i in range(n):
 root = find(i)
 # Use the original index from before sorting.
 original_index = self.logs[i]['original_index']
 if root not in event_groups:
 event_groups[root] = []
 event_groups[root].append(original_index)

 # Convert the groups dictionary to the final list of lists format.
 security_events = list(event_groups.values())

 # Sort logs within each event by their original index for deterministic output.
 for event in security_events:
 event.sort()

 # Create the reverse mapping from original log index to event ID.
 log_index_to_event_id = {}
 for event_id, event_indices in enumerate(security_events):
 for log_index in event_indices:
 log_index_to_event_id[log_index] = event_id

 return security_events, log_index_to_event_id