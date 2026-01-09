def rule_4_merge_event_cores_rule_for_mod_jk_worker_state_cha(log: dict) -> list[str]:
    """
    Identifies logs related to mod_jk worker state changes and extracts a common key
    based on the worker name. This allows grouping of trigger and subsequent related events.
    """
    keys = []
    template = log.get('EventTemplate')
    if not template:
        return []

    trigger_templates = {
        "jk2_init() Found child <*>...",
        "jk2_init() Can't find child <*>..."
    }

    merge_templates = {
        "workerEnv.init() ok <*>",
        "mod_jk child init <*> <*>",
        "mod_jk child workerEnv in error state <*>"
    }

    should_extract_key = False
    if template in trigger_templates:
        # Trigger events always generate a key.
        should_extract_key = True
    elif template in merge_templates:
        # Subsequent events only generate a key if they lack an 'ip' address.
        if log.get('ip') is None:
            should_extract_key = True

    if should_extract_key:
        params = log.get('Parameters')
        # All relevant templates have the worker name as the first parameter.
        if params and len(params) > 0:
            worker_name = params[0]
            # Create a specific, shared key for this logical event group.
            key = f"MODJK_WORKER_STATE_CHANGE_{worker_name}"
            keys.append(key)

    return keys