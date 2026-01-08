import collections
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

class EventProcessor:
    """
    Groups raw log entries into logical security events based on heuristics
    like Process ID (PID), Source IP, and time proximity.
    """

    def __init__(self, logs: List[Dict]):
        """
        Initializes the EventProcessor with a list of log dictionaries.

        Args:
            logs: A list of dictionaries, where each dictionary represents a log entry.
        """
        self.logs = logs

    def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
        """
        Groups raw logs into logical security events.

        This method implements a single-pass clustering algorithm using a
        Union-Find (Disjoint Set Union) data structure. It correlates logs based on
        shared Process IDs (PIDs) and, as a secondary heuristic, shared source IPs
        for specific attack patterns within a tight time window.

        The algorithm works as follows:
        1.  Logs are sorted chronologically.
        2.  Each log starts in its own cluster (set).
        3.  The script iterates through the sorted logs, attempting to merge the
            current log's cluster with a recent, related cluster.
        4.  **PID Correlation (Strong Heuristic):** If a log shares a PID with a
            log seen recently, they are merged into the same cluster. This is
            effective for tracking single sessions.
        5.  **IP Correlation (Weaker Heuristic):** If PID correlation doesn't apply,
            the script checks for IP-based correlation. To avoid incorrectly grouping
            unrelated events from the same IP (e.g., behind a NAT), this is only
            applied if both the current and recent log from that IP match templates
            commonly associated with authentication attacks (e.g., brute-force attempts).
        6.  "Active session" trackers for PIDs and IPs are updated as logs are
            processed, creating an implicit sliding window for correlation.

        Returns:
            A tuple containing:
            - security_events: A list of lists, where each inner list is a
              cluster of original log indices.
            - log_index_to_event_id: A dictionary mapping each original log
              index to its corresponding event (cluster) ID.
        """
        if not self.logs:
            return [], {}

        num_logs = len(self.logs)

        # --- Union-Find Data Structure (nested for encapsulation) ---
        parent = list(range(num_logs))
        size = [1] * num_logs

        def find(i: int) -> int:
            """Finds the representative of the set containing element i with path compression."""
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]

        def union(i: int, j: int):
            """Merges the sets containing elements i and j using union-by-size."""
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                if size[root_i] < size[root_j]:
                    root_i, root_j = root_j, root_i
                parent[root_j] = root_i
                size[root_i] += size[root_j]

        # --- Preprocessing and Sorting ---
        logs_with_meta = []
        for i, log in enumerate(self.logs):
            try:
                ts_str = log.get('Timestamp')
                if ts_str:
                    ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    logs_with_meta.append({'original_index': i, 'data': log, 'ts': ts})
            except (ValueError, TypeError):
                # Skip logs with malformed or missing timestamps
                continue
        
        logs_with_meta.sort(key=lambda x: x['ts'])

        # --- Clustering Logic ---
        pid_sessions: Dict[str, Tuple[int, datetime]] = {}
        ip_sessions: Dict[str, Tuple[int, datetime]] = {}

        PID_TIMEOUT = timedelta(seconds=120)
        IP_TIMEOUT = timedelta(seconds=30)

        # Templates related to authentication failures, often seen in brute-force attacks.
        AUTH_FAILURE_TEMPLATES = {
            '1', '2', '3', '4',  # Invalid user sequence
            '7', '8',             # Failed password for valid user
            '9', '10', '11', '12' # "Too many failures" sequence
        }

        for log_meta in logs_with_meta:
            original_index = log_meta['original_index']
            log_data = log_meta['data']
            current_ts = log_meta['ts']

            pid = log_data.get('PID')
            ip = log_data.get('ip')
            template_id = log_data.get('TemplateID')

            merged = False

            # 1. PID-based correlation (highest priority)
            if pid and pid in pid_sessions:
                rep_idx, last_ts = pid_sessions[pid]
                if current_ts - last_ts <= PID_TIMEOUT:
                    union(original_index, rep_idx)
                    merged = True

            # 2. IP-based correlation (for attacks where PIDs change)
            if not merged and ip and ip in ip_sessions:
                rep_idx, last_ts = ip_sessions[ip]
                if current_ts - last_ts <= IP_TIMEOUT:
                    last_log_template = self.logs[rep_idx].get('TemplateID')
                    if template_id in AUTH_FAILURE_TEMPLATES and last_log_template in AUTH_FAILURE_TEMPLATES:
                        union(original_index, rep_idx)
                        merged = True

            # Update session trackers with the current log's info.
            # The representative index is the root of the log's current cluster.
            new_root_idx = find(original_index)
            if pid:
                pid_sessions[pid] = (new_root_idx, current_ts)
            if ip:
                ip_sessions[ip] = (new_root_idx, current_ts)
        
        # --- Formatting the Output ---
        clusters = collections.defaultdict(list)
        for i in range(num_logs):
            root = find(i)
            clusters[root].append(i)

        security_events = list(clusters.values())

        log_index_to_event_id = {}
        for event_id, indices in enumerate(security_events):
            for index in indices:
                log_index_to_event_id[index] = event_id

        return security_events, log_index_to_event_id