from typing import Dict, List, Optional

def rule_5_contextual_enrichment_rule_for_ipless_logs_for_log(log: Dict) -> List[str]:
 """
 Extracts a PID key for specific logs that lack direct source identifiers.

 This rule targets logs with specific TemplateIDs ([2, 3, 12]) that need
 context from other logs. The linking mechanism for this context is the
 Process ID (PID). This function extracts the PID as the linking key if the
 log matches the specified TemplateIDs.

 Args:
 log: A dictionary representing a single log entry.

 Returns:
 A list containing the formatted PID key (e.g., ['PID_12345']) if the
 log's TemplateID is in [2, 3, 12] and a PID exists. Otherwise, returns
 an empty list.
 """
 keys = []
 target_template_ids = {2, 3, 12}
 template_id = log.get('TemplateID')

 if template_id in target_template_ids:
 pid = log.get('PID')
 if pid is not None:
 keys.append(f"PID_{pid}")

 return keys