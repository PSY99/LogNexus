def rule_11_merge_event_cores_rule_for_device_node_operations_(log: Dict) -> List[str]:
    # Extract relevant fields with defaults
    event_template = log.get('EventTemplate', '')
    process_name = log.get('ProcessName', '')
    parameters = log.get('Parameters', [])
    ip = log.get('ip', '')
    rhost = log.get('rhost', [])

    # Define the target templates and process
    target_templates = [
        'removing device node <*>',
        'creating device node <*>',
        'device node removed'
    ]
    
    # Check if the event template matches any of the target templates
    if not any(template in event_template for template in target_templates):
        return []

    # Check if the process is 'udev'
    if process_name != 'udev':
        return []

    # Extract the device path from parameters (assuming it's the first non-empty parameter)
    device_path = None
    for param in parameters:
        if param and not any(blacklisted in param.lower() for blacklisted in ['unknown', 'null', 'none', 'invalid']):
            device_path = param.strip()
            break

    # If no valid device path found, return empty list
    if not device_path:
        return []

    # Format the key as "TYPE_value" where TYPE is derived from the event template
    # Use a consistent key type based on the action
    if 'removing' in event_template or 'device node removed' in event_template:
        key_type = 'DEVICE_NODE_REMOVAL'
    elif 'creating' in event_template:
        key_type = 'DEVICE_NODE_CREATION'
    else:
        key_type = 'DEVICE_NODE_MANAGEMENT'

    # Create the linking key using the format KEYTYPE_keyvalue
    # Use the device path as the value
    return [f"{key_type}_{device_path}"]