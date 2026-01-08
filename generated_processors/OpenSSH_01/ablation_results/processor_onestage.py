import sys
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

# It's good practice to increase the recursion limit when using a recursive
# implementation of Union-Find's `find` operation, especially with
# potentially long chains of events, to prevent RecursionError.
sys.setrecursionlimit(2000)

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
                  The structure is expected to be compatible with the problem description.
        """
        self.logs = logs

    def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
        """
        Clusters logs into security events using a single-pass, sliding-window
        approach with a Union-Find data structure.

        The method correlates logs based on two main heuristics within a defined
        time window:
        1.  **Same Process ID (PID):** Logs sharing the same PID are considered
            part of the same process session and are strongly correlated.
        2.  **Same Source IP:** Logs from the same source IP are grouped. This is
            effective for capturing related activities like brute-force attacks
            that may spawn multiple processes from a single attacker.

        The algorithm is designed to be efficient and robust:
        - It processes logs chronologically in a single pass.
        - A sliding time window limits comparisons to only recent logs.
        - The Union-Find data structure efficiently merges event clusters.
        - It gracefully handles missing or malformed data in log entries.

        Returns:
            A tuple containing:
            - security_events (List[List[int]]): A list of clusters, where each
              cluster is a list of original log indices belonging to that event.
            - log_index_to_event_id (Dict[int, int]): A mapping from each
              original log index to its corresponding event ID (the index in
              the security_events list).
        """
        if not self.logs:
            return [], {}

        # --- Step 1: Augment logs with original index and parsed datetime ---
        # This step is crucial for sorting and later reconstructing the
        # final result with original indices. It also makes time comparisons efficient.
        aug_logs = []
        for i, log in enumerate(self.logs):
            try:
                # Create a copy to avoid modifying the original input list of dicts
                log_copy = log.copy()
                log_copy['original_index'] = i
                # The timestamp is the primary key for ordering events.
                log_copy['_datetime'] = datetime.strptime(log['Timestamp'], '%Y-%m-%d %H:%M:%S')
                aug_logs.append(log_copy)
            except (ValueError, KeyError, TypeError):
                # Gracefully skip logs with malformed or missing timestamps.
                # This ensures the script is robust against imperfect data.
                continue

        # Sort logs chronologically. This is essential for the sliding window approach.
        aug_logs.sort(key=lambda x: x['_datetime'])
        
        n = len(aug_logs)
        if n == 0:
            return [], {}

        # --- Step 2: Initialize Union-Find Data Structure ---
        # `parent` array tracks the root of the set for each element.
        # `size` array is used for the union-by-size optimization.
        parent = list(range(n))
        size = [1] * n

        def find(i: int) -> int:
            """Finds the root of the set for element i with path compression."""
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

        # --- Step 3: Main Clustering Loop (Single-Pass with Sliding Window) ---
        # Define the time window for correlating events. 60 seconds is a
        # reasonable heuristic to group related but separate processes,
        # such as a rapid series of SSH login attempts from one IP.
        TIME_WINDOW = timedelta(seconds=60)

        for i in range(n):
            log_i = aug_logs[i]
            # Use .get() for safe access to potentially missing keys.
            pid_i = log_i.get('PID')
            ip_i = log_i.get('ip')
            ts_i = log_i['_datetime']

            # Iterate backwards through recent logs within the time window.
            for j in range(i - 1, -1, -1):
                log_j = aug_logs[j]
                ts_j = log_j['_datetime']

                # If the previous log is outside the window, stop searching for this log_i.
                if ts_i - ts_j > TIME_WINDOW:
                    break

                # --- Correlation Heuristics ---
                # The logic is self-contained within this loop as required.
                
                # Rule 1: Same Process ID. This is the strongest indicator
                # that two log entries belong to the same session.
                pid_j = log_j.get('PID')
                if pid_i is not None and pid_i == pid_j:
                    union(i, j)
                
                # Rule 2: Same Source IP. This links activities from the same
                # source, which is highly effective for grouping events like
                # brute-force attacks that span multiple PIDs.
                ip_j = log_j.get('ip')
                if ip_i is not None and ip_i == ip_j:
                    union(i, j)

        # --- Step 4: Format the Output ---
        # Group logs by their final root in the Union-Find structure.
        # The keys are the root of each cluster, and values are lists of
        # original log indices.
        clusters = defaultdict(list)
        for i in range(n):
            root = find(i)
            original_index = aug_logs[i]['original_index']
            clusters[root].append(original_index)

        # Convert the dictionary of clusters into the required list of lists.
        # Sorting the inner lists makes the output deterministic and easier to read.
        security_events = [sorted(v) for v in clusters.values()]

        # Create the mapping from original log index to the new event ID.
        log_index_to_event_id = {}
        for event_id, event_logs in enumerate(security_events):
            for log_index in event_logs:
                log_index_to_event_id[log_index] = event_id
                
        return security_events, log_index_to_event_id