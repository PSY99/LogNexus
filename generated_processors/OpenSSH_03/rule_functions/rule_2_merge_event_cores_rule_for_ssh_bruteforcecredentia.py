from typing import Dict, List

def rule_2_merge_event_cores_rule_for_ssh_bruteforcecredentia(log: Dict) -> List[str]:
 """
 [MERGE EVENT CORES Rule for SSH Brute-Force/Credential Stuffing] After initial grouping by PID, identify all 'Event Cores' from the 'sshd' process that contain authentication failure templates (e.g., 'Failed password for <*> from <*>', 'Invalid user <*> from <*>', 'pam_unix(sshd:auth): authentication failure'). If multiple such cores share the exact same Key Source Identifier (Source IP from the 'ip' or 'rhost' field) and occur within a continuous time window (e.g., 30 minutes), merge them into a single logical 'SSH Brute-Force Attempt' event. This rule reconstructs a sustained attack from a single actor that spans multiple server processes.
 """
 # Condition 1: The log must originate from the 'sshd' process.
 if log.get('ProcessName') != 'sshd':
 return []

 # Condition 2: The event template must indicate an authentication failure.
 event_template = log.get('EventTemplate', '')
 failure_signatures = [
 'Failed password for',
 'Invalid user',
 'authentication failure' # Catches 'pam_unix(sshd:auth): authentication failure'
 ]

 if not any(sig in event_template for sig in failure_signatures):
 return []

 # If conditions are met, extract the source IP/host as the linking key.
 keys = []
 source_identifiers = set()

 # Extract identifier from the 'ip' field.
 source_ip = log.get('ip')
 if source_ip:
 source_identifiers.add(source_ip)

 # Extract identifier(s) from the 'rhost' field.
 remote_hosts = log.get('rhost')
 if isinstance(remote_hosts, list):
 for host in remote_hosts:
 if host:
 source_identifiers.add(host)

 # Create a composite key for each unique source identifier found.
 # The key type "SSH_BRUTEFORCE_IP" signals the intent to group these events
 # as a single logical brute-force attempt from a specific source.
 for identifier in source_identifiers:
 keys.append(f"SSH_BRUTEFORCE_IP_{identifier}")

 return keys