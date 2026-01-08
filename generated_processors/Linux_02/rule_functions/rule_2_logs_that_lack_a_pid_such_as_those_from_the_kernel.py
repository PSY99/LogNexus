from typing import Dict, List


def rule_2_logs_that_lack_a_pid_such_as_those_from_the_kernel(log: Dict) -> List[str]:
    """
    Identifies logs from specific system processes that lack a PID and treats them
    as individual 'Event Cores'.
    """
    # The rule applies to logs that lack a PID. This includes logs where PID is
    # not present (None) or is 0 (often used for kernel/swapper processes).
    pid = log.get('PID')

    # The primary condition is that the log lacks a meaningful, positive PID.
    if pid:  # If PID is a positive integer, this rule does not apply.
        return []

    # The rule provides examples of processes to target. We'll use this list
    # to scope the rule to intended system logs.
    target_processes = {'kernel', 'network', 'syslog', 'rc'}
    process_name = log.get('ProcessName')

    # Check if the process name is one of the specified targets.
    if process_name and process_name in target_processes:
        # The rule states these are "individual, single-line 'Event Cores'".
        # To make them individual, we create a unique key based on the LogContent.
        # This ensures each unique log line is treated as its own event.
        log_content = log.get('LogContent')
        if log_content:
            # The key type "EVENTCORE" signifies that this log is a standalone event.
            return [f"EVENTCORE_{log_content}"]

    # If the conditions are not met, return an empty list.
    return []