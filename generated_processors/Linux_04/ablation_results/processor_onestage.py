import ast
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

class EventProcessor:
    """
    Groups raw logs into logical security events based on temporal and contextual heuristics.
    """

    class _DSU:
        """A simple Disjoint Set Union (DSU) data structure for clustering."""
        def __init__(self, n: int):
            self.parent = list(range(n))

        def find(self, i: int) -> int:
            """Finds the root of the set containing element i with path compression."""
            if self.parent[i] == i:
                return i
            self.parent[i] = self.find(self.parent[i])
            return self.parent[i]

        def union(self, i: int, j: int) -> None:
            """Merges the sets containing elements i and j."""
            root_i = self.find(i)
            root_j = self.find(j)
            if root_i != root_j:
                self.parent[root_j] = root_i

    def __init__(self, logs: List[Dict]):
        """
        Initializes the EventProcessor with a list of log dictionaries.

        Args:
            logs: A list of dictionaries, where each dictionary represents a log entry.
        """
        self.logs = logs

    def _parse_list_from_string(self, s: str) -> List[str]:
        """Safely parses a string representation of a list."""
        if isinstance(s, str) and s.startswith('[') and s.endswith(']'):
            try:
                return ast.literal_eval(s)
            except (ValueError, SyntaxError):
                return []
        return []

    def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
        """
        Groups logs into logical events using a single-pass clustering algorithm.

        The algorithm iterates through chronologically sorted logs and merges them into
        events based on a set of heuristics within a sliding time window. A Union-Find
        data structure efficiently manages the merging of events.

        Heuristics for merging logs:
        1.  **Same Process ID (PID):** Logs from the same process are strongly related.
        2.  **Same Network Source:** Logs sharing a source IP or remote host are grouped,
            useful for tracking external activities.
        3.  **Shared Entities:** Logs referencing the same non-generic entities (like
            usernames or file paths) in their parameters are linked.
        4.  **Co-occurring System Events:** Logs without a PID that occur in very close
            succession are grouped, capturing system-wide events like boot or shutdown
            sequences.

        Returns:
            A tuple containing:
            - A list of events, where each event is a list of original log indices.
            - A dictionary mapping each original log index to its corresponding event ID.
        """
        num_logs = len(self.logs)
        if num_logs == 0:
            return [], {}

        # 1. Pre-process logs: add original index and parse timestamps
        processed_logs = []
        for i, log_data in enumerate(self.logs):
            log = log_data.copy()
            log['original_index'] = i
            try:
                log['Timestamp'] = datetime.strptime(log['Timestamp'], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                log['Timestamp'] = datetime.min
            processed_logs.append(log)

        # 2. Sort logs chronologically for the sliding window approach
        processed_logs.sort(key=lambda x: x['Timestamp'])

        # 3. Initialize DSU for clustering
        dsu = self._DSU(num_logs)

        # 4. Define constants for heuristics
        MAIN_TIME_WINDOW = timedelta(seconds=10)
        SYSTEM_EVENT_WINDOW = timedelta(seconds=2)
        GENERIC_PARAMS = {'kernel', 'root', 'user', 'daemon', 'system', ''}

        # 5. Main clustering loop
        for i in range(num_logs):
            log_i = processed_logs[i]
            
            # Look ahead at subsequent logs within the time window
            for j in range(i + 1, num_logs):
                log_j = processed_logs[j]

                time_delta = log_j['Timestamp'] - log_i['Timestamp']
                if time_delta > MAIN_TIME_WINDOW:
                    break

                should_union = False

                # Heuristic 1: Same Process ID (PID)
                pid_i = log_i.get('PID')
                if pid_i is not None and pid_i == log_j.get('PID'):
                    should_union = True

                # Heuristic 2: Same Network Source (IP/rhost)
                if not should_union:
                    ip_i = log_i.get('ip')
                    if ip_i and ip_i == log_j.get('ip'):
                        should_union = True
                    else:
                        rhost_i = set(self._parse_list_from_string(log_i.get('rhost', '[]')))
                        if rhost_i:
                            rhost_j = set(self._parse_list_from_string(log_j.get('rhost', '[]')))
                            if rhost_i.intersection(rhost_j):
                                should_union = True
                
                # Heuristic 3: Shared non-generic parameters
                if not should_union:
                    params_i_list = self._parse_list_from_string(log_i.get('Parameters', '[]'))
                    # Exclude the first parameter, which is often the process name
                    if len(params_i_list) > 1:
                        params_j_list = self._parse_list_from_string(log_j.get('Parameters', '[]'))
                        if len(params_j_list) > 1:
                            meaningful_params_i = set(params_i_list[1:]) - GENERIC_PARAMS
                            if meaningful_params_i:
                                meaningful_params_j = set(params_j_list[1:]) - GENERIC_PARAMS
                                if meaningful_params_i.intersection(meaningful_params_j):
                                    should_union = True

                # Heuristic 4: Co-occurring PID-less system events
                if not should_union:
                    if log_i.get('PID') is None and log_j.get('PID') is None:
                        template_i = log_i.get('EventTemplate', '')
                        template_j = log_j.get('EventTemplate', '')
                        is_system_state_change = any(kw in template_i or kw in template_j for kw in ['reboot', 'shutdown', 'restart.'])
                        
                        if is_system_state_change or time_delta <= SYSTEM_EVENT_WINDOW:
                            should_union = True

                if should_union:
                    dsu.union(i, j)

        # 6. Build final event groups from the DSU structure
        clusters: Dict[int, List[int]] = {}
        for i in range(num_logs):
            root = dsu.find(i)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(processed_logs[i]['original_index'])

        security_events = list(clusters.values())
        
        for event in security_events:
            event.sort()

        # 7. Create the mapping from original log index to event ID
        log_index_to_event_id: Dict[int, int] = {}
        for event_id, event_logs in enumerate(security_events):
            for log_index in event_logs:
                log_index_to_event_id[log_index] = event_id
                
        return security_events, log_index_to_event_id