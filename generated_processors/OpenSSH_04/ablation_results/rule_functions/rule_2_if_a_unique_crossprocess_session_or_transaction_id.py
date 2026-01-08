def rule_2_if_a_unique_crossprocess_session_or_transaction_id(log: Dict) -> List[str]:
 import re

 keys = []
 parameters = log.get('Parameters')

 if not parameters or not isinstance(parameters, list):
 return []

 # Regex for full UUID match
 uuid_pattern = re.compile(
 r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
 )

 # Regex to find and extract values from common session/transaction key-value pairs
 session_kv_pattern = re.compile(
 r'(?:session|sid|jsessionid|transaction(?:id)?|txid|traceid|requestid)\s*[:=]\s*([a-zA-Z0-9-]{8,})',
 re.IGNORECASE
 )

 for param in parameters:
 if not isinstance(param, str):
 continue

 # Heuristic 1: Check for explicit key-value patterns like "session=..." or "txid:..."
 # This is the most reliable indicator.
 kv_match = session_kv_pattern.search(param)
 if kv_match:
 identifier = kv_match.group(1)
 keys.append(f"SESSIONID_{identifier}")
 continue # Found a strong match, move to the next parameter

 # Heuristic 2: Check if the parameter itself is a UUID.
 if uuid_pattern.fullmatch(param):
 keys.append(f"SESSIONID_{param}")
 continue

 # Heuristic 3: General check for long, mixed alphanumeric strings that are
 # likely to be identifiers. This is a fallback for unknown ID formats.
 # - Length between 10 and 64 to avoid short, ambiguous strings and overly long ones.
 # - Must contain at least one letter and one digit.
 # - Excludes common path/file characters and hex prefixes to reduce false positives.
 if 10 <= len(param) <= 64 and \
 not param.startswith('0x') and \
 '.' not in param and \
 '/' not in param and \
 '\\' not in param and \
 any(c.isalpha() for c in param) and \
 any(c.isdigit() for c in param):
 keys.append(f"SESSIONID_{param}")

 return list(set(keys))