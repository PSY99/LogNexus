def rule_3_merge_event_cores_rule_for_network_attackscan_afte(log: Dict) -> List[str]:
 # Define failure templates to match
 failure_templates = {
 'authentication failure',
 'connection unexpectedly closed',
 'peer died',
 'probable port-scan',
 'Connection from <*> on illegal port',
 'Authentication failed from <*>',
 'Client hung up - probable port-scan',
 'getpeername (ftpd): Transport endpoint is not connected'
 }

 # Extract relevant fields
 template = log.get('EventTemplate', '').lower()
 ip = log.get('ip', '')
 rhost_list = log.get('rhost', [])
 parameters = log.get('Parameters', [])

 # Blacklist of common non-relevant parameter values
 blacklist = {'root', 'admin', 'user', 'guest', 'unknown', 'localhost', '127.0.0.1'}

 # Check if the template matches any failure pattern
 if not any(pattern.lower() in template for pattern in failure_templates):
 return []

 # Build list of keys based on IP or rhost
 keys = []

 # Add IP-based key if available and valid
 if ip and ip.strip() and ip != '0.0.0.0':
 keys.append(f"IP_{ip}")

 # Add rhost-based keys if available
 for host in rhost_list:
 if host and host.strip() and host != 'localhost' and host != '127.0.0.1':
 # Normalize FQDN-like entries
 normalized_host = host.strip().lower()
 if normalized_host not in blacklist:
 keys.append(f"RHOST_{normalized_host}")

 # Extract non-blacklisted parameters as potential linking keys
 for param in parameters:
 if param and param.strip() and param.lower() not in blacklist:
 keys.append(f"PARAM_{param.strip()}")

 # If no valid keys, return empty list
 if not keys:
 return []

 # Return all extracted keys with composite format using IP or rhost as source identifier
 # Since we are stateless, we only extract keys based on current log entry
 # Composite key format: TYPE_SOURCE_value
 # We use IP or RHOST as the source identifier
 result = []
 for key in keys:
 if key.startswith("IP_"):
 result.append(key)
 elif key.startswith("RHOST_"):
 result.append(key)

 # Also include a composite key combining IP and Template if both exist
 if ip and ip.strip() and ip != '0.0.0.0':
 template_key = f"IP_TEMPLATE_{ip}_{template}"
 result.append(template_key)

 # Include rhost + template composite if rhost exists
 for host in rhost_list:
 if host and host.strip() and host != 'localhost' and host != '127.0.0.1':
 normalized_host = host.strip().lower()
 if normalized_host not in blacklist:
 rhost_template_key = f"RHOST_TEMPLATE_{normalized_host}_{template}"
 result.append(rhost_template_key)

 return result