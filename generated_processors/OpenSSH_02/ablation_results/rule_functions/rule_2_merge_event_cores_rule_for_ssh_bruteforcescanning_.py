def rule_2_merge_event_cores_rule_for_ssh_bruteforcescanning_(log: Dict) -> List[str]:
 """
 Extracts a source IP-based key from sshd failure logs.

 This rule targets logs from the 'sshd' process that indicate an
 authentication failure. For such logs, it extracts the source IP address
 from the 'rhost' or 'ip' fields. The extracted IP is used as a linking
 key to merge multiple failure events from the same source, which is
 indicative of a brute-force or scanning attack.

 The key format is "IP_<source_ip>".
 """
 # Condition 1: The log must be from the 'sshd' process.
 if log.get('ProcessName') != 'sshd':
 return []

 # Condition 2: The log's event template must indicate a failure.
 event_template = log.get('EventTemplate')
 if not isinstance(event_template, str):
 return []

 failure_template_prefixes = (
 'Failed password for',
 'pam_unix(sshd:auth): authentication failure',
 'Invalid user',
 'input_userauth_request: invalid user'
 )

 is_failure_log = any(event_template.startswith(prefix) for prefix in failure_template_prefixes)

 if not is_failure_log:
 return []

 # If both conditions are met, extract the Key Source Identifier (IP address).
 # The rule specifies 'rhost' or 'ip' fields.
 keys = []
 source_ips = set()

 # Extract from 'rhost' (which is a list of strings)
 rhosts = log.get('rhost')
 if isinstance(rhosts, list):
 for host in rhosts:
 if isinstance(host, str) and host:
 source_ips.add(host)

 # Extract from 'ip' (which is a string)
 ip_addr = log.get('ip')
 if isinstance(ip_addr, str) and ip_addr:
 source_ips.add(ip_addr)

 # Format the extracted IPs into the required "KEYTYPE_keyvalue" format.
 for ip in source_ips:
 keys.append(f"IP_{ip}")

 return keys