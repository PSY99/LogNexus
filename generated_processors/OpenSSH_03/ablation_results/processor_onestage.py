import json
from datetime import datetime, timedelta
import ast
from typing import List, Dict, Tuple, Optional, Any

class EventProcessor:
    """
    Groups raw log entries into logical security events based on heuristics
    like PID, source IP, user, and time proximity.
    """

    def __init__(self, logs: List[Dict]):
        """
        Initializes the processor with a list of log dictionaries.

        Args:
            logs: A list of dictionaries, where each dictionary represents a log entry.
        """
        self.logs = logs
        self.processed_logs: List[Dict] = []
        self._preprocess_logs()

    def _extract_user(self, log: Dict) -> Optional[str]:
        """
        Extracts a username from a log's parameters based on its template.
        Handles missing keys and parsing errors gracefully.
        """
        template_id = log.get('TemplateID')
        params_str = log.get('Parameters')

        if template_id is None or not isinstance(params_str, str):
            return None

        try:
            # Safely evaluate the string representation of the list
            params = ast.literal_eval(params_str)
            if not isinstance(params, list):
                return None
        except (ValueError, SyntaxError):
            return None

        # Mapping from TemplateID to the index of the username in Parameters
        user_param_map = {
            '1': 1,   # Invalid user <*> from <*>
            '2': 1,   # input_userauth_request: invalid user <*> [preauth]
            '4': 1,   # Failed password for invalid user <*> from <*> port <*> ssh2
            '7': -1,  # pam_unix... user=<*>
            '8': 1,   # Failed password for <*> from <*> port <*> ssh2
            '9': 2,   # message repeated <*> times: [ Failed password for <*> from ... ]
            '10': 1,  # Disconnecting: Too many authentication failures for <*>
            '11': -1, # PAM <*> more authentication failures... user=<*>
            '17': 1,  # Accepted password for <*> from <*> port <*> ssh2
            '18': 1,  # pam_unix(sshd:session): session opened for user <*> by ...
            '20': 1,  # pam_unix(sshd:session): session closed for user <*>
        }

        idx = user_param_map.get(str(template_id))
        if idx is not None:
            try:
                user = params[idx]
                return str(user) if user is not None else None
            except IndexError:
                return None
        return None

    def _preprocess_logs(self):
        """
        Parses and sorts logs, adding derived fields for easier processing.
        This method populates `self.processed_logs`.
        """
        for i, log in enumerate(self.logs):
            processed = log.copy()
            processed['original_index'] = i

            # Gracefully parse timestamp
            ts = log.get('Timestamp')
            if isinstance(ts, str):
                try:
                    # Handle potential fractional seconds which might appear
                    ts_format = '%Y-%m-%d %H:%M:%S'
                    if '.' in ts:
                        ts_format += '.%f'
                    processed['datetime'] = datetime.strptime(ts, ts_format)
                except ValueError:
                    processed['datetime'] = datetime.min # Fallback for unexpected formats
            elif isinstance(ts, datetime):
                 processed['datetime'] = ts
            else:
                 processed['datetime'] = datetime.min # Default for missing or invalid type

            # Extract user and add it to the processed log
            processed['user'] = self._extract_user(log)
            
            self.processed_logs.append(processed)

        # Sort logs by timestamp to enable efficient time-window-based processing
        self.processed_logs.sort(key=lambda x: x['datetime'])

    def cluster_events(self) -> Tuple[List[List[int]], Dict[int, int]]:
        """
        Clusters logs into security events using a single-pass algorithm with a
        sliding time window and a Union-Find data structure.

        The clustering logic is based on a set of prioritized heuristics:
        1.  **PID Match (High Confidence):** Logs with the same Process ID within
            the time window are strongly correlated and part of the same session.
        2.  **IP & User Match (High-Medium Confidence):** Catches related activities
            from the same user at the same IP, even if PIDs differ (e.g., rapid
            reconnection attempts).
        3.  **IP Match for Auth Events (Medium Confidence):** Groups authentication-related
            logs from the same IP. This is effective for identifying brute-force
            or scanning activities where an attacker tries multiple usernames.

        Returns:
            A tuple containing:
            - security_events: A list of lists, where each inner list contains the
                               original indices of logs belonging to one event.
            - log_index_to_event_id: A dictionary mapping each log's original index
                                     to its assigned event ID (the index in security_events).
        """
        num_logs = len(self.logs)
        if num_logs == 0:
            return [], {}

        # --- Union-Find Data Structure ---
        # parent[i] stores the parent of element i. Initially, every element is its own parent.
        parent = list(range(num_logs))

        def find(i: int) -> int:
            """Finds the root of the set containing element i with path compression."""
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]

        def union(i: int, j: int):
            """Merges the sets containing elements i and j."""
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_j] = root_i

        # --- Clustering Configuration ---
        TIMEOUT = timedelta(seconds=15)
        # Templates related to authentication attempts, failures, and warnings
        AUTH_RELATED_TEMPLATES = {
            '0', '1', '2', '3', '4', '7', '8', '9', '10', '11', '12', '14', '16', '25'
        }

        # --- Main Clustering Loop ---
        for i in range(len(self.processed_logs)):
            log_i_data = self.processed_logs[i]
            original_i = log_i_data['original_index']

            # Look backwards in a sliding time window
            for j in range(i - 1, -1, -1):
                log_j_data = self.processed_logs[j]
                original_j = log_j_data['original_index']

                # Stop if the previous log is outside the time window
                if log_i_data['datetime'] - log_j_data['datetime'] > TIMEOUT:
                    break

                # --- Correlation Heuristics (in order of confidence) ---
                # Rule 1: PID Match (High Confidence)
                pid_i = log_i_data.get('PID')
                if pid_i is not None and pid_i == log_j_data.get('PID'):
                    union(original_i, original_j)
                    continue

                # Rule 2: IP & User Match (High-Medium Confidence)
                ip_i = log_i_data.get('ip')
                user_i = log_i_data.get('user')
                if (ip_i is not None and ip_i == log_j_data.get('ip') and
                    user_i is not None and user_i == log_j_data.get('user')):
                    union(original_i, original_j)
                    continue

                # Rule 3: IP Match for Auth-related events (Medium Confidence)
                tid_i = str(log_i_data.get('TemplateID', ''))
                tid_j = str(log_j_data.get('TemplateID', ''))
                if (ip_i is not None and ip_i == log_j_data.get('ip') and
                    tid_i in AUTH_RELATED_TEMPLATES and
                    tid_j in AUTH_RELATED_TEMPLATES):
                    union(original_i, original_j)
                    continue

        # --- Final Grouping ---
        # Group original indices by their root parent.
        groups: Dict[int, List[int]] = {}
        for i in range(num_logs):
            root = find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(i)

        # Convert the groups dictionary to the required list of lists format.
        security_events = list(groups.values())
        
        # Sort logs within each event by their original index for readability
        for event in security_events:
            event.sort()

        # Create the reverse mapping from log index to event ID.
        log_index_to_event_id: Dict[int, int] = {}
        for event_id, indices in enumerate(security_events):
            for log_index in indices:
                log_index_to_event_id[log_index] = event_id

        return security_events, log_index_to_event_id