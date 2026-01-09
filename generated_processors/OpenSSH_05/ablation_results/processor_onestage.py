import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from ast import literal_eval

class EventProcessor:
    """
    Groups raw log entries into logical security events based on heuristics
    like Process ID (PID), Source IP, User, and time proximity.
    """

    def __init__(self, logs: List[Dict]):
        """
        Initializes the EventProcessor with a list of log entries.

        Args:
            logs: A list of dictionaries, where each dictionary represents a log entry.
        """
        # Store original logs to return original indices
        self.original_logs = logs
        # Pre-process logs for easier and more consistent data access
        self.logs = self._preprocess_logs(logs)
        self.num_logs = len(self.logs)
        # Initialize parent array for the Union-Find data structure.
        # Each log starts as its own parent, representing a unique event.
        self.parent = list(range(self.num_logs))

    def _find_user(self, log: Dict) -> Optional[str]:
        """
        Extracts a username from a log's parameters based on its event template.
        This uses a set of heuristics tailored to common SSH log formats.

        Args:
            log: A pre-processed log dictionary.

        Returns:
            The extracted username as a string, or None if not found.
        """
        template = log.get("EventTemplate", "")
        params = log.get("Parameters", [])

        if not isinstance(params, list) or not params:
            return None

        try:
            # Heuristic 1: "Invalid user <user> from <ip>" or "Failed password for invalid user <user>..."
            if "invalid user" in template.lower():
                return params[1]
            # Heuristic 2: "Accepted password for <user> from <ip>..."
            elif "accepted password for" in template.lower():
                return params[1]
            # Heuristic 3: "pam_unix(...): ... user=<user>"
            elif "pam_unix" in template and "user=" in template:
                return params[-1]
            # Heuristic 4: "pam_unix(...): session ... for user <user>"
            elif "session opened for user" in template or "session closed for user" in template:
                return params[1]
            # Heuristic 5: "Too many authentication failures for <user>"
            elif "too many authentication failures for" in template.lower():
                return params[1]
        except (IndexError, TypeError):
            # Gracefully handle cases where parameters don't match expectations
            return None
        
        return None

    def _preprocess_logs(self, logs: List[Dict]) -> List[Dict]:
        """
        Cleans and standardizes the raw log data.
        - Converts timestamp strings to datetime objects.
        - Parses parameter strings into lists.
        - Converts PID strings to integers.
        - Extracts a canonical 'User' field.
        - Adds the original index for later reference.

        Args:
            logs: The raw list of log dictionaries.

        Returns:
            A list of processed log dictionaries.
        """
        processed_logs = []
        for i, log in enumerate(logs):
            new_log = log.copy()

            # Convert 'Timestamp' string to datetime object
            ts = new_log.get("Timestamp")
            if isinstance(ts, str):
                try:
                    new_log["Timestamp"] = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    new_log["Timestamp"] = None
            
            # Parse 'Parameters' string into a list
            params = new_log.get("Parameters")
            if isinstance(params, str):
                try:
                    new_log["Parameters"] = literal_eval(params)
                except (ValueError, SyntaxError):
                    new_log["Parameters"] = []
            
            # Convert 'PID' to integer
            pid = new_log.get("PID")
            if pid is not None:
                try:
                    new_log["PID"] = int(pid)
                except (ValueError, TypeError):
                    new_log["PID"] = None
            
            # Extract and add a unified 'User' field
            new_log["User"] = self._find_user(new_log)
            
            # Keep track of the original index
            new_log["OriginalIndex"] = i
            
            processed_logs.append(new_log)
        return processed_logs

    def _find_set(self, i: int) -> int:
        """
        Finds the representative (root) of the set containing element i,
        with path compression for optimization.

        Args:
            i: The index of the element.

        Returns:
            The index of the representative of the set.
        """
        if self.parent[i] == i:
            return i
        self.parent[i] = self._find_set(self.parent[i])
        return self.parent[i]

    def _union_sets(self, i: int, j: int):
        """
        Merges the sets containing elements i and j.

        Args:
            i: The index of the first element.
            j: The index of the second element.
        """
        i_id = self._find_set(i)
        j_id = self._find_set(j)
        if i_id != j_id:
            # A simple union; could be improved with union-by-rank/size,
            # but is sufficient for this task.
            self.parent[j_id] = i_id

    def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
        """
        Groups logs into security events using a single-pass clustering algorithm.
        It uses a Union-Find data structure to efficiently merge related logs into events.
        The logic prioritizes strong links (PID) over weaker ones (IP/User, IP).

        Returns:
            A tuple containing:
            - security_events: A list of lists, where each inner list contains the
              original indices of logs belonging to a single security event.
            - log_index_to_event_id: A dictionary mapping each log's original index
              to its assigned event ID.
        """
        # Time window to consider logs as part of the same event.
        TIME_WINDOW = timedelta(seconds=60)

        # Tracking dictionaries to store the last seen log index and timestamp for each entity.
        # key -> (log_index, timestamp)
        pid_map: Dict[int, Tuple[int, datetime]] = {}
        ip_user_map: Dict[Tuple[str, str], Tuple[int, datetime]] = {}
        ip_map: Dict[str, Tuple[int, datetime]] = {}

        # --- Main Clustering Loop (Single Pass) ---
        for i in range(self.num_logs):
            current_log = self.logs[i]
            current_ts = current_log.get("Timestamp")
            
            if not current_ts:
                continue  # Skip logs that couldn't be timestamped.

            pid = current_log.get("PID")
            ip = current_log.get("ip")
            user = current_log.get("User")

            linked = False

            # 1. Primary Link: Process ID (PID)
            # Logs from the same process are almost always part of the same event.
            if pid is not None and pid in pid_map:
                last_idx, last_ts = pid_map[pid]
                if current_ts - last_ts <= TIME_WINDOW:
                    self._union_sets(last_idx, i)
                    linked = True
            
            # 2. Secondary Link: Source IP and User
            # Connects activities from the same user@IP, even if PIDs change (e.g., brute-force).
            if not linked and ip and user and (ip, user) in ip_user_map:
                last_idx, last_ts = ip_user_map[(ip, user)]
                if current_ts - last_ts <= TIME_WINDOW:
                    self._union_sets(last_idx, i)
                    linked = True

            # 3. Tertiary Link: Source IP only
            # A weaker link, used cautiously to group related but anonymous activities.
            if not linked and ip and ip in ip_map:
                last_idx, last_ts = ip_map[ip]
                # Use a tighter time window and content check to avoid over-grouping.
                if current_ts - last_ts <= timedelta(seconds=15):
                    last_log = self.logs[last_idx]
                    # Heuristic: Group if both logs are related to authentication attempts.
                    is_auth_related_curr = any(kw in current_log.get("EventTemplate", "").lower() for kw in ["fail", "invalid", "disconnect", "auth"])
                    is_auth_related_last = any(kw in last_log.get("EventTemplate", "").lower() for kw in ["fail", "invalid", "disconnect", "auth"])
                    if is_auth_related_curr and is_auth_related_last:
                         self._union_sets(last_idx, i)
                         linked = True

            # Update tracking maps with the current log's information.
            # This makes it the most recent point of contact for that entity.
            if pid is not None:
                pid_map[pid] = (i, current_ts)
            if ip and user:
                ip_user_map[(ip, user)] = (i, current_ts)
            if ip:
                ip_map[ip] = (i, current_ts)

        # --- Post-processing: Format the output ---
        # Group log indices by their final representative in the Union-Find structure.
        clusters: Dict[int, List[int]] = {}
        for i in range(self.num_logs):
            root = self._find_set(i)
            if root not in clusters:
                clusters[root] = []
            # Append the original index, not the processed one.
            clusters[root].append(self.logs[i]["OriginalIndex"])

        # Convert the dictionary of clusters into the required list of lists.
        security_events: List[List[int]] = list(clusters.values())
        
        # Sort logs within each event and sort the events themselves for deterministic output.
        for event in security_events:
            event.sort()
        security_events.sort(key=lambda x: x[0])

        # Create the final mapping from original log index to the new event ID.
        log_index_to_event_id: Dict[int, int] = {}
        for event_id, event_logs in enumerate(security_events):
            for log_idx in event_logs:
                log_index_to_event_id[log_idx] = event_id

        return security_events, log_index_to_event_id