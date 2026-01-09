import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional

# The prompt requires a self-contained script.
# All logic must be within the class.

class EventProcessor:
    """
    Groups raw log entries into logical security events based on heuristics
    like PID, source IP, and time proximity.
    """

    def __init__(self, logs: List[Dict[str, Any]]):
        """
        Initializes the EventProcessor with a list of log dictionaries.

        Args:
            logs: A list of dictionaries, where each dictionary represents a log entry.
        """
        self.raw_logs = logs
        
        # The input logs might not be sorted. We need to process them chronologically.
        # We pair each log with its original index to reconstruct the final output.
        # This handles potential malformed 'Timestamp' entries by skipping them.
        
        temp_logs_with_indices = []
        for i, log in enumerate(logs):
            ts_str = log.get('Timestamp')
            if ts_str and isinstance(ts_str, str):
                try:
                    # The specified format is "YYYY-MM-DD HH:MM:SS"
                    ts_obj = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    # Store the log, its parsed timestamp, and its original index
                    temp_logs_with_indices.append(((log, ts_obj), i))
                except ValueError:
                    # Skip logs with invalid timestamp format
                    continue
        
        # Sort by the parsed datetime object to ensure chronological processing
        self.sorted_logs_with_indices = sorted(
            temp_logs_with_indices,
            key=lambda item: item[0][1]
        )

    def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
        """
        Clusters logs into security events using a single-pass algorithm with
        a Union-Find data structure.

        Logs are correlated based on two main heuristics:
        1.  **Process ID (PID):** Logs sharing the same PID within a generous time
            window are considered part of the same process session. This is the
            strongest correlation signal.
        2.  **Source IP Address:** Logs from the same IP in rapid succession are
            grouped together. This is effective for identifying activities like
            brute-force scans that may spawn multiple processes.

        The Union-Find data structure efficiently merges these related log entries
        into transitive clusters.

        Returns:
            A tuple containing:
            - security_events: A list of lists, where each inner list contains the
                               original indices of logs belonging to a single event.
            - log_index_to_event_id: A dictionary mapping each log's original index
                                     to its assigned event ID (which is the index
                                     into the security_events list).
        """
        if not self.sorted_logs_with_indices:
            return [], {}

        num_logs = len(self.sorted_logs_with_indices)
        # The parent array for the Union-Find data structure.
        # Initially, each log is in its own set, represented by its own index.
        parent = list(range(num_logs))

        # --- Union-Find Helper Functions (self-contained as required) ---
        def find_set(i: int) -> int:
            """Finds the representative of the set containing element i with path compression."""
            if parent[i] == i:
                return i
            parent[i] = find_set(parent[i])
            return parent[i]

        def unite_sets(i: int, j: int):
            """Merges the sets containing elements i and j."""
            root_i = find_set(i)
            root_j = find_set(j)
            if root_i != root_j:
                # A simple union is sufficient; union by size/rank is not critical here.
                parent[root_j] = root_i

        # --- Heuristics Configuration ---
        # A long timeout for PIDs to capture entire user sessions.
        PID_TIMEOUT = timedelta(minutes=15)
        # A short timeout for IPs to link rapid, related events like scans.
        IP_TIMEOUT = timedelta(seconds=10)

        # --- Correlation Maps ---
        # These maps store the most recent sorted index and timestamp for each entity.
        # {entity_key: (sorted_index, timestamp)}
        pid_map: Dict[int, Tuple[int, datetime]] = {}
        ip_map: Dict[str, Tuple[int, datetime]] = {}

        # --- Main Clustering Loop ---
        # Iterate through the chronologically sorted logs.
        for i in range(num_logs):
            (current_log, current_ts), _ = self.sorted_logs_with_indices[i]
            
            # Gracefully extract PID and IP, handling missing keys and type variations.
            current_pid: Optional[int] = None
            pid_val = current_log.get('PID')
            if pid_val is not None:
                try:
                    current_pid = int(pid_val)
                except (ValueError, TypeError):
                    pass  # PID is not a valid integer, treat as None

            current_ip: Optional[str] = current_log.get('ip')

            # 1. Correlate by Process ID (strongest link)
            if current_pid is not None and current_pid in pid_map:
                prev_idx, prev_ts = pid_map[current_pid]
                # If the time gap is within the timeout, unite the log clusters.
                if current_ts - prev_ts <= PID_TIMEOUT:
                    unite_sets(i, prev_idx)
            
            # 2. Correlate by Source IP (for related sessions like scans)
            if current_ip is not None and current_ip in ip_map:
                prev_idx, prev_ts = ip_map[current_ip]
                # If the time gap is small, unite the log clusters.
                if current_ts - prev_ts <= IP_TIMEOUT:
                    unite_sets(i, prev_idx)

            # After checking for correlations, update the maps with the current log's info.
            # This ensures the next log compares against the most recent predecessor.
            if current_pid is not None:
                pid_map[current_pid] = (i, current_ts)
            if current_ip is not None:
                ip_map[current_ip] = (i, current_ts)
        
        # --- Post-processing: Group indices based on Union-Find results ---
        # `clusters` will map a root representative to a list of original log indices.
        clusters = defaultdict(list)
        for i in range(num_logs):
            # Find the root representative for the set containing log `i`.
            root = find_set(i)
            # Get the original index of the log from our sorted list.
            _, original_index = self.sorted_logs_with_indices[i]
            clusters[root].append(original_index)

        # --- Format the final output as per the contract ---
        security_events = list(clusters.values())
        
        # Sort logs within each event by their original index for consistency and readability.
        for event in security_events:
            event.sort()

        log_index_to_event_id = {}
        for event_id, event_indices in enumerate(security_events):
            for log_original_index in event_indices:
                log_index_to_event_id[log_original_index] = event_id

        return security_events, log_index_to_event_id