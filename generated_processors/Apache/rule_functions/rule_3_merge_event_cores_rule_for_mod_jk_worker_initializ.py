from typing import Dict, List


def rule_3_merge_event_cores_rule_for_mod_jk_worker_initializ(log: Dict) -> List[str]:
    """
    Identifies logs related to mod_jk worker initialization sequences.

    This rule creates a linking key based on a worker name for a specific set of
    mod_jk log templates. It distinguishes between a "trigger" log and subsequent
    "related" logs.

    - Trigger: A log with an EventTemplate starting with "jk2_init()".
    - Related: Logs with specific templates like "workerEnv.init() ok <*>" that
               do NOT have an associated 'ip' address.

    The key is formed using the worker name extracted from the log's parameters,
    allowing an orchestrator to group the entire initialization sequence.
    """
    event_template = log.get('EventTemplate', '')
    parameters = log.get('Parameters', [])
    ip_address = log.get('ip')

    if not event_template or not parameters:
        return []

    trigger_prefix = "jk2_init()"
    related_templates = {
        "workerEnv.init() ok <*>",
        "mod_jk child init <*> <*>",
        "mod_jk child workerEnv in error state <*>"
    }

    worker_name = None

    # Case 1: The log is a trigger event for the sequence.
    if event_template.startswith(trigger_prefix):
        # The worker name is expected to be the first parameter.
        worker_name = parameters[0]

    # Case 2: The log is a related event in the sequence.
    elif event_template in related_templates:
        # This part of the sequence is only linked if it lacks an IP address.
        if not ip_address:
            # Assume the worker name is the first parameter for these templates as well.
            worker_name = parameters[0]

    # If a worker name was successfully extracted, create the linking key.
    if worker_name:
        # The key links all parts of a single worker's initialization sequence.
        key = f"MODJK_WORKER_INIT_{worker_name}"
        return [key]

    return []