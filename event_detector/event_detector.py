# event_detector/event_detector.py

import os
import logging
import json
from datetime import timedelta, datetime
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from . import code_generator

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from utils.llm_utils import call_llm_api, initialize_llm_client


################################################################################
# --- DATASET-SPECIFIC KNOWLEDGE BASE (VERSION 2.0 - DATA-DRIVEN) ---
################################################################################

DATASET_GUIDANCE = {
    "BGL": {
        "context": """
            You are analyzing logs from a **Blue Gene/L (BGL) supercomputer**. These logs describe hardware and low-level system events on physical nodes.
            **Key Log Fields**: Your primary focus should be on `Location` (e.g., 'R02-M1-N0-C:J12-U11'), `EventTemplate`, `Category` (e.g., 'RAS'), `Subsystem` (e.g., 'KERNEL'), and `Level` (e.g., 'INFO', 'FATAL').
            **Core Logic**: Unlike typical OS logs, BGL logs often lack a Process ID (PID). The central organizing principle is the **physical node**. Events are typically collections of status messages or errors occurring on a specific node within a short time frame.
            """,
        "examples": """
            {{
                "mandatory_rules": [
                    "Group all logs that share the **exact same `Location` AND the exact same `EventTemplate`** and occur within the **same second** into a foundational 'Event Core'. This captures high-frequency event bursts as a single atomic unit."
                ],
                "heuristic_rules": [
                    "**[MERGE CORES by Shared Location]** This is the most important rule for BGL. After initial grouping, identify all 'Event Cores' that share the **exact same `Location` field value**. If they occur within a moderate time window (e.g., 5 minutes), **merge** them into a single logical 'Node Health Event'. The `Location` is the primary **Correlation Identifier** for BGL.",
                    "**[MERGE CORES for High-Frequency Bursts]** If multiple logs with the **exact same `EventTemplate`** (e.g., 'instruction cache parity error corrected') and the **exact same `Location`** occur in a very tight time window (e.g., 30 seconds), merge them into a single 'Error Burst' event. This rule explicitly groups the common pattern of event storms.",
                    "**[BOUNDARY Rule by Severity Change]** An Event Core containing a log with a `Level` of 'FATAL', 'SEVERE', or 'FAILURE' marks a critical state transition. This log should be the definitive end of its logical event. Do NOT merge it with subsequent, unrelated 'INFO' logs from the same node, even if they are close in time.",
                    "**[KEY DIMENSION SPLIT Rule]** This is a critical boundary rule. Even if logs occur close in time, if their **`Location` field is different**, they MUST be treated as belonging to **new, separate logical events**. Each node represents a distinct physical context that should not be mixed."
                ]
            }}
            """
    },
    "Hadoop": {
        "context": """
            You are analyzing logs from a distributed **Hadoop/YARN MapReduce** system. Events represent stages of a distributed computation.
            **Key Log Fields**: The logs are rich with hierarchical identifiers. You MUST pay close attention to: `application_id`, `job_id`, `task_id`, `task_attempt_id`, and `container_id`. Also note `Component` (the logging thread/module) and `JavaClass`.
            **Core Logic**: A single logical operation (e.g., running an application) generates logs across many components and processes. Your goal is to reassemble this distributed activity.
            *   `task_attempt_id` is the best **Instance Identifier**, representing a single execution attempt.
            *   `application_id`, `job_id`, `task_id`, `container_id` are powerful **Correlation Identifiers** to link different instances.
            """,
        "examples": """
            {{
                "mandatory_rules": [
                    "Group all logs sharing the **exact same `task_attempt_id`** into a foundational 'Event Core'. This is the most reliable `Instance Identifier` for a single, non-splittable unit of work in Hadoop."
                ],
                "heuristic_rules": [
                    "**[MERGE CORES by Application Lifecycle]** This is the highest-level grouping. After initial grouping, identify all 'Event Cores' that share the **exact same `application_id`**. **Merge** them to reconstruct the entire lifecycle of a MapReduce application, from submission (e.g., template 'Created MRAppMaster for application <*>') to completion (e.g., 'job_... completed successfully' or 'failed'). The `application_id` is the ultimate **Correlation Identifier**.",
                    "**[MERGE CORES by Job/Task Context]** As a mid-level grouping, merge 'Event Cores' that share the same `job_id` or `task_id` if they occur within a reasonable time window (e.g., 10 minutes) and are part of the same `application_id`.",
                    "**[MERGE CORES by Container Activity]** Merge logs related to the same `container_id`, such as allocation, usage, and release (e.g., template 'Releasing unassigned and invalid container'), even if they have different `task_attempt_id`s, as a container's lifecycle is a distinct event.",
                    "**[BOUNDARY Rule by State Change (Timeout)]** A log with the template `Diagnostics report from <*>: ... Timed out ...` marks a definitive failure for the corresponding `task_attempt_id`. This log and its associated core should NOT be merged with subsequent retry attempts, which will have a new `task_attempt_id`.",
                    "**[KEY DIMENSION SPLIT Rule]** This is a critical boundary rule. Even if logs are close in time, if they belong to a different **`application_id`**, they MUST be treated as belonging to **new, separate logical events**. Each application is a distinct context."
                ]
            }}
            """
    },
    "Linux": {
        "context": """
            You are analyzing logs from a general-purpose **Linux/Unix system**. These logs originate from various sources like network services (SSH, web servers), system daemons (cron, syslog), kernel messages, and user applications.
            **Key Entities**: The primary actors and resources are **Users**, **Processes (PID)**, **Network Sources** (IPs, hostnames, URLs), and **System Resources** (files, devices).
            **Core Logic**: Events in this environment are diverse. Some are tied to a single process, while others (like a network attack or a distributed file operation) involve multiple processes coordinated by an external actor or a shared resource. Your goal is to correctly identify both types of events. In addition, logs without PID for behaviors such as system restart and service restart should also be correctly classified as an event.
            """,
        "examples": """
            {{
                "mandatory_rules": [
                    "Group all logs sharing the **exact same Process ID (PID)** into a foundational 'Event Core'. This grouping is absolute and these cores must never be split internally.",
                    "Logs that lack a PID, such as those from the 'kernel', 'network', or init scripts, are to be treated as individual, single-line 'Event Cores' pending further analysis by heuristic rules."
                ],
                "heuristic_rules": [
                    "[MERGE EVENT CORES Rule for Network Attack/Scan] After initial PID-based grouping, identify all 'Event Cores' containing failure templates like 'authentication failure', 'connection unexpectedly closed', 'peer died', 'probable port-scan', or 'Connection from <*> on illegal port'. Merge all such cores, regardless of their original PID or process name, if they share the exact same Key Source Identifier (IP address or rhost FQDN) and occur within a 15-minute sliding window. This reconstructs a single logical 'Network Attack' event from a single actor.",
                    
                    "[BOUNDARY Rule by State Change] An 'Event Core' representing a successful login (e.g., 'sshd(pam_unix): session opened for user') must not be merged with any preceding 'Network Attack' event, even if they share the same Key Source Identifier. This successful session initiates its own distinct 'User Session' event.",

                    "[MERGE EVENT CORES Rule for System Boot] Identify a log with EventTemplate 'syslogd <*>: restart.' or 'Linux version <*>' as the trigger for a 'System Boot' event. Greedily merge this trigger with all subsequent logs from the 'kernel' process and any 'Event Cores' whose EventTemplate contains 'startup succeeded' or 'Version <*> Starting'. The merge window for this event ends after 5 minutes or upon the first user session log (e.g., 'sshd: session opened'), whichever comes first.",

                    "[MERGE EVENT CORES Rule for System Shutdown] Identify a log with EventTemplate 'shutting down for system reboot' as the trigger for a 'System Shutdown' event. Greedily merge this trigger with all subsequent 'Event Cores' whose EventTemplate contains 'shutdown succeeded', 'terminating', 'exiting', or 'received signal 15'. The event boundary is the appearance of a subsequent 'System Boot' trigger log.",

                    "[STATE TRANSITION BOUNDARY Rule for Sessions] An 'Event Core' created by the mandatory PID rule is defined as a complete 'User Session' event if it contains both a 'session opened for user' log and a corresponding 'session closed for user' log. All logs between these two state transition markers belong to this single event.",
                    
                    "[MERGE EVENT CORES Rule for Service Restart] Identify an 'Event Core' indicating a service shutdown (e.g., 'named: exiting'). If another 'Event Core' from the same process name (e.g., 'named') indicating a startup (e.g., 'starting BIND') occurs within a 60-second window, merge both cores into a single logical 'Service Restart' event.",
                    
                    "[MERGE EVENT CORES Rule for Kernel Errors] Identify a log with an EventTemplate containing 'page allocation failure'. Greedily merge all subsequent, contiguous logs from the 'kernel' process that match the stack trace template '[<*>] <*>+<*>' into a single 'Kernel Panic Trace' event. Separately, merge multiple distinct 'Event Cores' with the template 'Out of Memory: Killed process <*>' that occur within a 10-minute window into a single 'System Under Memory Pressure' event.",
                    
                    "[KEY DIMENSION SPLIT Rule] When applying merging rules based on Key Source Identifiers, if the identifier's value changes (e.g., from IP '1.2.3.4' to '5.6.7.8'), a new logical event must be started. 'Event Cores' from distinct external actors must never be merged."
                ]
            }}
            """
    },

    "Apache": {
        "context": """
            You are analyzing logs from the **Apache HTTP Server**, a widely used open-source web server. These logs capture incoming HTTP requests, internal module activities, error conditions, and service lifecycle events.
            **Key Log Fields**: The most critical fields include:
            - `ip`: The client IP address (the **Key Source Identifier** for external activity).
            - `EventTemplate`: Structured representation of log messages (e.g., `[client 192.168.1.1] File does not exist: /var/www/html/secret.txt`).
            - `PID`: Process ID of the Apache worker handling the request (used for atomic grouping).
            **Core Logic**: 
            - Apache logs mix **external user-driven events** (HTTP requests) with **internal system events** (module initialization, restarts, shutdowns).
            - External events are correlated by **client IP (`ip`)** and temporal proximity, while internal events often lack an `ip` and are grouped by process context or sequential templates.
            - A single logical event may span multiple PIDs (e.g., a web scanner probing many URLs across different worker processes), so heuristic merging based on source IP is essential.
            - Service lifecycle events (restarts, shutdowns) are self-contained sequences that must be reconstructed as atomic state transitions.
        """,
        "examples": """
            {{
                "mandatory_rules": [
                    "Group all logs sharing the **exact same Process ID (PID)** into a foundational 'Event Core'. This grouping is absolute and these cores must never be split internally."
                ],
                "heuristic_rules": [
                    "**[MERGE EVENT CORES Rule for Web Scanning Activity]** After initial grouping, identify 'Event Cores' containing logs with templates like `[client <*>] File does not exist: <*>`, `[client <*>] script not found or unable to stat: <*>`, or `[client <*>] Directory index forbidden by rule: <*>`. If multiple such cores share the **exact same Key Source Identifier (the `ip` field)** and occur within a continuous session (e.g., with no more than 60 seconds between consecutive logs), **merge** them into a single logical 'Web Scanning/Probing' event. This rule reconstructs the activity of a single external actor across potentially many server processes.",
                    "**[MERGE EVENT CORES Rule for `mod_jk` Worker Initialization]** Identify a log with `EventTemplate` `jk2_init() Found child <*>...` or `jk2_init() Can't find child <*>...` as a trigger. Greedily merge this with subsequent, adjacent logs (within a 2-second window) that match related templates like `workerEnv.init() ok <*>`, `mod_jk child init <*> <*>` and `mod_jk child workerEnv in error state <*>` and **lack a Key Source Identifier (`ip`)**. This forms a single logical 'mod_jk Worker Initialization' event, capturing the full start-up or failure sequence of a single worker.",
                    "**[MERGE EVENT CORES Rule for Service Restart]** Identify a log with `EventTemplate: 'Graceful restart requested, doing restart'` as the trigger for a 'Service Restart' event. Greedily merge all subsequent logs indicating service configuration and startup (e.g., `Digest: ...`, `LDAP: ...`, `mod_python: ...`, `mod_security/...`) until a log matching `EventTemplate: 'Apache/<*> configured -- resuming normal operations'` is found. This boundary log is included, and the event is closed, reconstructing the entire state transition of the service restart.",
                    "**[MERGE EVENT CORES Rule for Mass Shutdown Notifications]** Identify a log with `EventTemplate: 'mod_jk2 Shutting down'`. Merge all subsequent, consecutive logs that share this **exact same `EventTemplate`** and occur within a tight time window (e.g., 15 seconds) into a single logical 'mod_jk Shutdown' event. The event is bounded by the first log with a different template or a timeout.",
                    "**[KEY DIMENSION SPLIT Rule]** For events driven by external actors, if the **Key Source Identifier (the `ip` field)** changes between two log entries or 'Event Cores', they MUST be treated as belonging to **new, separate logical events**, even if they are temporally adjacent and share the same `EventTemplate`. Each unique `ip` value defines a distinct actor context.",
                    "**[BOUNDARY Rule by Timeout]** For any event being constructed via heuristic merging (such as a 'Web Scanning/Probing' event), if no new related log or 'Event Core' is found that meets the merge criteria within a predefined session timeout (e.g., 60 seconds), the event is considered complete and is closed."
                ]
            }}
        """
    },

    "OpenSSH": {
        "context": """
            You are analyzing logs from a general-purpose Linux/Unix system, likely related to network services like SSH. Events are often related to user sessions, authentication attempts, and process activities. The key entities are **Users**, **Source IPs**, and **Processes (PIDs)**.
            """,
        "examples": """
            {{
                "mandatory_rules": [
                    "Group all logs sharing the **exact same Process ID (PID)** into a foundational 'Event Core'. This grouping is absolute and these cores must never be split internally.",
                    "Group all logs sharing the **exact same unique Session ID** (e.g., 'session-ABC-123') into a foundational 'Event Core'. This is the most reliable form of atomic grouping."
                ],
                "heuristic_rules": [
                    "**[MERGE EVENT CORES Rule for SSH Brute-Force]** After initial grouping by PID, identify all 'Event Cores' consisting of 'sshd(pam_unix): authentication failure' logs. If multiple such cores, **even those with different PIDs**, share the **exact same Key Source Identifier (the full value of the 'rhost' field, e.g., 'www.buller.hoover.fresno.k12.ca.us')** and occur within a tight time window (e.g., 15 minutes), **merge** them into a single logical 'SSH Brute-Force Attempt' event. This rule explicitly connects multiple processes to a single external actor, overcoming the initial PID-based separation.",
                    
                    "**[MERGE EVENT CORES Rule for High-Frequency Internal Failures]** Identify multiple 'Event Cores' from the **same process name** (e.g., `sshd(pam_unix)`) that share the **exact same failure-related EventTemplate** (e.g., `check pass; user unknown`) and **lack a Key Source Identifier**. If they occur within a very tight time window (e.g., 30 seconds), **merge** them into a single logical 'High-Frequency Internal Failure' event.",

                    "**[MERGE EVENT CORES Rule for System Boot]** Identify a log with `EventTemplate: \"Linux version <*>\"` as the trigger for a 'System Boot' event. Greedily merge **all** subsequent logs from the 'kernel' process and **any** 'Event Cores' indicating service startups (e.g., `rpc.statd[*] Version <*> Starting`) that occur within the next 5 minutes into this single logical event.",

                    "**[BOUNDARY Rule by State Change]** An 'Event Core' representing a successful login ('sshd: session opened for user') acts as a hard boundary. **Do NOT merge** this success core with any preceding 'Brute-Force Attempt' event, even if they share the same Key Source Identifier. The successful session, identified by its new, stable PID, forms its own distinct event.",
                    
                    "**[KEY DIMENSION SPLIT Rule]** Even if logs occur close in time, if the activity is external (like login attempts) and the **Key Source Identifier (e.g., Source IP, client hostname, or FQDN)** changes, the resulting 'Event Cores' MUST be treated as belonging to **new, separate logical events**. Each unique identifier represents a distinct actor context.",
                    
                    "**[STATE TRANSITION BOUNDARY Rule]** An 'Event Core' containing a log that indicates a clear session finalization (e.g., 'sshd: session closed for user') marks the definitive end for the logical event associated with that session's PID.",
                    
                    "**[TIME-BASED MERGE Rule]** If two 'Event Cores' (e.g., one from a client log, one from a server log) share the **exact same HDFS Block ID** and their timestamps are within seconds of each other, merge them. Here, the Block ID is the key to link distributed perspectives of a single operation."
                ]
            }}
            """
    },
    "Zookeeper": {
        "context": """
            You are analyzing logs from an **Apache ZooKeeper** distributed coordination service. These logs capture a wide range of activities:
            - **Server startup and configuration** (reading config, binding ports, setting timeouts)
            - **Leader election dynamics** (state transitions: LOOKING → LEADING/FOLLOWING, peer communication)
            - **Client session lifecycle** (connection, session establishment, revalidation, expiration, closure)
            - **Data consistency operations** (snapshotting, log replay, DIFF/SNAP synchronization with leader)
            - **Graceful or abrupt shutdown sequences**
            - **Network and I/O errors** (broken pipes, connection resets, election timeouts)

            **Key Log Fields**:
            - `sessionid`: Unique 64-bit hex ID (e.g., `0x10000000d`) — primary **Instance Identifier** for client sessions.
            - `client`: Client address (e.g., `/10.0.0.5:54321`) — **Key Source Identifier** for external actors.
            - `EventTemplate`: Structured message indicating semantic action (e.g., 'Established session', 'LOOKING', 'Expiring session').
            - Server identity context is often implicit in logs like 'My id = 1' or 'Follower sid: 2'.

            **Core Logic**:
            - A **logical event** is a sequence representing a single, meaningful action or state transition, such as: (1) Server Startup, (2) Leader Election, (3) Follower Synchronization, or (4) a Client Session Lifecycle.
            - Events are driven by state changes (e.g., LOOKING → LEADING) and component context (e.g., logs from the `[main]` thread for startup, `[LearnerHandler]` for sync).
            - Logs without `sessionid` or `client` typically belong to **system-level operational events** (startup, election, shutdown).
        """,
        "examples": """
            {
                "mandatory_rules": [
                    "**[M1: Client Session Core]** Group all logs sharing the **exact same `sessionid`** into a 'Client Session Event Core'. This is the most reliable identifier for a single client session and this core must never be split.",
                    "**[M2: Follower Sync Core]** Group all logs sharing the **exact same `ThreadName` that follows the pattern `LearnerHandler-<IP>:<PORT>`** into a 'Follower Synchronization Event Core'. This creates a perfect atomic unit for a single follower's sync process and must never be split.",
                    "**[M3: Quorum Connection Core]** Group all logs sharing the same unique connection identifier embedded in `ThreadName` (e.g., `SendWorker:<ID>`, `RecvWorker:<ID>`) into a 'Quorum Connection Event Core'. This isolates communication on a specific peer-to-peer channel.",
                    "**[M4: Fallback Core]** Any log that does not meet the criteria of the rules above is initially treated as an individual, single-line 'System Event Core'. These are the building blocks for heuristic merging."
                ],
                "heuristic_rules": [
                    "**[H1: MERGE CORES for Server Startup]**: Identify a 'System Event Core' with `ThreadName: \"main\"` and `EventTemplate`: 'Reading configuration from: <*>' as a trigger. Greedily merge this with all subsequent, contiguous 'System Event Cores' from the `ThreadName: \"main\"` that describe configuration and initialization. **This event definitively ENDS and is bounded by the first appearance of a log with `EventTemplate`: 'LOOKING'.** The 'LOOKING' log itself belongs to the *next* event (Leader Election).",

                    "**[H2: MERGE CORES for Leader Election Cycle]**: Identify a 'System Event Core' with `EventTemplate`: 'LOOKING' as the trigger. Merge all subsequent 'System Event Cores' and 'Quorum Connection Event Cores' related to the election process (e.g., 'New election. My id = <*>', 'Notification', 'Cannot open channel to <*>'). **This event definitively ENDS and is bounded by the first appearance of a log indicating a final state ('LEADING' or 'FOLLOWING').** The final state log is included in this event, closing it.",

                    "**[H3: MERGE CORES for Leader Initialization]**: Immediately following a 'Leader Election' event that concludes with a 'LEADING' log, identify that 'LEADING' log as a trigger. Merge it with all subsequent 'System Event Cores' that describe the leader's setup (e.g., 'Created server with tickTime <*>...', 'TCP NoDelay set to: true'). **This event ENDS upon the first log from a different context** (e.g., a 'Follower Synchronization Event Core' or a client connection log) or after a short timeout (e.g., 10 seconds).",

                    "**[H4: MERGE CORES for Follower Initialization]**: Immediately following a 'Leader Election' event that concludes with a 'FOLLOWING' log, identify that 'FOLLOWING' log as a trigger. Merge it with all subsequent 'System Event Cores' that describe the follower's setup (e.g., 'following leader'). **This event ENDS upon the first log indicating a successful connection to the leader** or after a short timeout (e.g., 30 seconds).",

                    "**[H5: ISOLATION Rule for Follower Synchronization]**: A 'Follower Synchronization Event Core' (formed by Mandatory Rule M2) is treated as a **complete, standalone logical event**. It perfectly captures the entire process of a single follower syncing with the leader. No further merging is needed.",

                    "**[H6: MERGE CORES for Graceful Shutdown]**: Identify a 'System Event Core' with `EventTemplate`: 'shutdown called' as the trigger. Greedily merge all subsequent 'System Event Cores' indicating component exits (e.g., 'CommitProcessor exited loop!', 'SyncRequestProcessor exited!') until a final '******* GOODBYE <*> ********' log is found. This forms a complete 'Server Shutdown' event.",

                    "**[B1: BOUNDARY Rule by Activity Gap (Timeout)]**: This is a crucial global rule. For any event being constructed via heuristic merging (like Startup, Election, etc.), if no new related log is found that meets the merge criteria within a **predefined time window (e.g., 60 seconds)**, the event is considered complete and is closed. This prevents unrelated logs from being incorrectly merged across large time gaps.",

                    "**[B2: BOUNDARY Rule by Session State]**: A log with `EventTemplate`: 'Expiring session <*> ...' or 'Exception causing close of session <*> ...' marks the definitive end of the client session event identified by that `sessionid`.",

                    "**[I1: ISOLATION Rule for Quorum Connection Issues]**: A 'Quorum Connection Event Core' (formed by Mandatory Rule M3) that contains error logs like 'Connection broken for id <*>' is treated as a **complete, isolated event** representing a peer connection failure. It should not be merged further unless it occurs strictly within the timeframe of a 'Leader Election Cycle' (Rule H2).",

                    "**[I2: ISOLATION Rule for Standalone System Errors]**: A 'System Event Core' with `Level: ERROR` or `FATAL` (e.g., 'Unexpected Exception') that cannot be logically merged into an ongoing event based on the rules above should be treated as a **standalone 'System Error' event**."
                ]
            }
        """
    }
}




################################################################################
# --- PROMPT DEFINITION ---
################################################################################

PROMPT_FOR_NL_RULES = """
You are a top-tier security analyst and system architect, specializing in log analysis and event correlation. Your task is to analyze the following raw log samples and define a set of precise rules for an automated event detection engine.

### 1. System Context & Core Objective: The "Minimal, Coherent Event Unit" ###
{dataset_context}
Your ultimate goal is to define rules that group logs into the **smallest possible, logically complete event units**. An "event" is not just a loose collection of related logs; it's a sequence representing a single, meaningful action, state transition, or a significant system-level occurrence (like a boot sequence).

### 2. Understanding the Input Data (CRITICAL) ###
The log samples provided below include a special field called **`_SamplingContext`**. You MUST use this field to understand the intent behind each log:

*   **`STRATEGY_DIVERSITY`**: These logs were selected because they represent a **unique log template**. Treat them as distinct examples of different event types.
*   **`STRATEGY_CONTEXT`**: These logs were selected because they appeared in a **dense time cluster** with other logs. **Pay close attention to the relationship between these logs and their neighbors.** They are specifically provided to show you how logs merge into a single event (e.g., a burst of errors, a multi-step transaction).
*   **`STRATEGY_FALLBACK`**: Additional logs to ensure sufficient volume.

The core philosophy is a two-step process:
1.  **Atomic Grouping**: First, use unbreakable identifiers (like a PID, a unique transaction, thread or container) to form "Event Cores". These cores are foundational and must never be split.
2.  **Contextual Merging**: Second, apply intelligent rules to merge these distinct Event Cores into a single, logical event when context dictates they represent parts of a larger, singular action.

### Rule Hierarchy & Philosophy ###
You must generate a hierarchical set of rules divided into two categories: **Mandatory Rules** and **Heuristic/Boundary Rules**.

1.  **Mandatory Rules (Forming Event Cores)**:
    *   **Philosophy**: These rules are based on **unique, high-cardinality identifiers** that deterministically link logs. They perform the initial, non-negotiable grouping, creating the foundational "Event Cores". An Event Core created by a mandatory rule can **never** be split.
    *   **Examples**: A specific Process ID (PID), a unique session identifier.

2.  **Heuristic & Boundary Rules (Merging Cores & Defining Boundaries)**:
    *   **Philosophy & Purpose: Overcoming Initial Separation**: This is where the real intelligence of the system lies. The primary purpose of these rules is to analyze the distinct 'Event Cores' (often created based on different PIDs) and decide when to **merge** them. **This is the crucial step to reconstruct a logical event that spans multiple processes.** A brute-force attack, for instance, is a single logical event from one attacker, even if the server spawns a dozen different processes to handle the attempts. Your rules must capture this logic.
    *   **Mechanisms**:
        *   **Merging by Actor/Target**: These rules rely on analyzing **Key Source Identifiers** and other shared attributes across different Event Cores. 
            **A Key Source Identifier is a field that represents the external actor or target of an interaction. This includes Source IPs, client hostnames, and Fully Qualified Domain Names (FQDNs) often found in fields like 'rhost' or 'from'.** Merging is justified when multiple Event Cores share the same Key Source Identifier and other contextual clues (e.g., tight timestamps, consistent log templates).
        *   **Merging by Event Type**: Some events, by their nature, span multiple processes and log entries. Rules should identify a trigger log and then greedily consume related subsequent logs based on process name, keywords, and a time window.
        *   **Defining Boundaries**: Rules must also use state transitions (e.g., a successful login after failures) or timeouts to prevent incorrect, over-extended merging.

### Log Samples ###
{log_samples_string}

### Output Format ###
Your output MUST be a valid JSON object with two keys: "mandatory_rules" and "heuristic_rules". Each key's value should be a JSON array of strings, where each string is a single, well-defined rule. Provide ONLY the JSON object, without any additional explanations or markdown.
JSON FORMATTING RULES:
Ensure the entire output is a single, well-formed JSON object.
All strings within the JSON must be enclosed in double quotes (").
Any literal backslash \ characters inside a string MUST be escaped as \\.
Do not add any text or explanations outside of the JSON object.

### Example of High-Quality, Hierarchical Rules (Focus on Core Formation & Merging) ###
{dataset_specific_examples}

"""



# ==============================================================================
# 辅助函数: 通用热点评分函数 (放置在类外部，因为它是一个纯函数)
# ==============================================================================
def calculate_hotspot_score_final(window_logs: List[Dict]) -> float:
    """
    最终版、完全通用的热点评分函数。
    它基于日志密度、模板多样性（熵）和参数值多样性。
    它假设每条日志有一个 'Parameters' 字段，其值为一个列表。
    """
    num_logs = len(window_logs)
    if num_logs == 0:
        return 0.0

    # --- 特征1: 模板多样性 (Template Diversity) using Entropy ---
    templates = [log['EventTemplate'] for log in window_logs]
    if not templates:
        template_entropy = 0
    else:
        # 使用 pandas 计算 value_counts 更高效
        template_counts = pd.Series(templates).value_counts()
        template_props = template_counts / num_logs
        template_entropy = -np.sum(template_props * np.log2(template_props))

    # --- 特征2: 参数值多样性 (Parameter Value Diversity) ---
    all_param_values = set()
    for log in window_logs:
        params = log.get('Parameters')
        if isinstance(params, list):
            all_param_values.update(params)
    
    num_unique_params = len(all_param_values)

    # --- 最终得分计算 ---
    # 使用 log1p (log(x+1)) 来平滑数值，避免极端值影响，并处理0值情况。
    density_score = np.log1p(num_logs)
    template_diversity_score = template_entropy + 1
    param_diversity_score = np.log1p(num_unique_params) + 1

    score = density_score * template_diversity_score * param_diversity_score
    return score


################################################################################
# --- DETECTOR CLASS ---
################################################################################

class MetaProgrammedDetector:
    """
    Orchestrates the entire meta-programming workflow to generate and apply an event detector.
    This class is the main entry point for the dynamic event detection process.
    """
    def __init__(self, config: Config, client: Any):
        """
        Initializes the detector with configuration and an LLM client.
        :param config: A Config object with all necessary paths and settings.
        :param client: An initialized LLM API client.
        """
        self.config = config
        self.client = client
        logging.info(f"MetaProgrammedDetector initialized for dataset '{config.dataset}'.")
        logging.info(f"Artifacts will be stored in: {config.artifacts_dir}")

    def _format_log_for_llm(self, log: Dict[str, Any], context_tag: str = 'random') -> str:
        """Formats a single log into a JSON string for the LLM (omitting PID)."""
        log_data = log.copy()
        if context_tag:
            log_data['_SamplingContext'] = context_tag
        return json.dumps({k: str(v) for k, v in log_data.items() if v is not None and v != 'N/A'})

    def _generate_and_save_sample(self, logs: List[Dict[str, Any]]) -> str:
        """
        Stage 1: Template-First Sampling with Contextual Deepening.
        Now includes 'Sampling Context' tagging.
        """
        logging.info("--- Stage 1: Generating sample with Context-Aware Tagging... ---")
        if not logs:
            return ""

        target_size = self.config.detector_sample_size
        
        try:
            sorted_logs = sorted(logs, key=lambda x: x['Timestamp'])
        except Exception as e:
            logging.error(f"Sort error: {e}")
            return ""
            
        all_templates_set = {log['EventTemplate'] for log in sorted_logs}

        # --- Pass 1: Scoring (不变) ---
        # ... (保持原有的聚类评分逻辑不变)
        session_timeout = timedelta(seconds=self.config.detector_session_gap_seconds)
        all_clusters = []
        if sorted_logs:
            start_idx = 0
            for i in range(1, len(sorted_logs)):
                if (sorted_logs[i]['Timestamp'] - sorted_logs[i-1]['Timestamp']) >= session_timeout:
                    cluster_logs = sorted_logs[start_idx:i]
                    if cluster_logs:
                        score = calculate_hotspot_score_final(cluster_logs)
                        all_clusters.append({'score': score, 'logs': cluster_logs})
                    start_idx = i
            last_cluster_logs = sorted_logs[start_idx:]
            if last_cluster_logs:
                score = calculate_hotspot_score_final(last_cluster_logs)
                all_clusters.append({'score': score, 'logs': last_cluster_logs})
        
        all_clusters.sort(key=lambda x: x['score'], reverse=True)

        # --- 【关键修改】引入 sample_annotations 字典来记录采样原因 ---
        final_samples_map = {} 
        sample_annotations = {} # Key: LogContent (or ID), Value: Strategy Tag
        template_representatives = {} 

        # --- Pass 2 & 3: Diversity Sampling (标记为 DIVERSITY) ---
        logging.info("  Pass 2 & 3: Selecting representatives (Diversity)...")
        
        for cluster in all_clusters:
            for log in cluster['logs']:
                template = log['EventTemplate']
                if template not in template_representatives:
                    template_representatives[template] = log
        
        covered_templates = set(template_representatives.keys())
        if len(covered_templates) < len(all_templates_set):
            for log in sorted_logs:
                template = log['EventTemplate']
                if template not in covered_templates:
                    template_representatives[template] = log
                    covered_templates.add(template)
        
        for log in template_representatives.values():
            key = log['LogContent']
            final_samples_map[key] = log
            # 标记为多样性样本
            sample_annotations[key] = "STRATEGY_DIVERSITY: Unique Template Representative"
        
        # --- Pass 4: Contextual Deepening (标记为 CONTEXT) ---
        if len(final_samples_map) < target_size:
            logging.info(f"  Pass 4: Contextual deepening (Context)...")
            templates_from_deepened_hotspots = set()
            novelty_threshold = self.config.detector_hotspot_novelty_threshold

            for cluster in all_clusters:
                if len(final_samples_map) >= target_size:
                    break

                cluster_templates = {log['EventTemplate'] for log in cluster['logs']}
                if not cluster_templates:
                    continue
                
                new_templates = cluster_templates - templates_from_deepened_hotspots
                novelty_score = len(new_templates) / len(cluster_templates)
                
                if novelty_score >= novelty_threshold:
                    templates_from_deepened_hotspots.update(cluster_templates)
                    
                    for log in cluster['logs']:
                        if len(final_samples_map) >= target_size:
                            break
                        key = log['LogContent']
                        if key not in final_samples_map:
                            final_samples_map[key] = log
                            # 标记为上下文样本
                            sample_annotations[key] = "STRATEGY_CONTEXT: Time-Window Cluster Member"

        # --- Pass 5: Fallback (标记为 FALLBACK) ---
        if len(final_samples_map) < target_size:
            logging.info(f"  Pass 5: Fallback filling...")
            for cluster in all_clusters:
                if len(final_samples_map) >= target_size:
                    break
                for log in cluster['logs']:
                    if len(final_samples_map) >= target_size:
                        break
                    key = log['LogContent']
                    if key not in final_samples_map:
                        final_samples_map[key] = log
                        sample_annotations[key] = "STRATEGY_FALLBACK"

        # --- Finalization ---
        final_samples = sorted(list(final_samples_map.values()), key=lambda x: x['Timestamp'])
        if len(final_samples) > target_size:
            final_samples = final_samples[:target_size]

        try:
            with open(self.config.sampled_logs_path, 'w', encoding='utf-8') as f:
                for log in final_samples:
                    f.write(json.dumps(log, default=str) + '\n')
        except IOError:
            raise IOError(f"Failed to write sampled logs to {self.config.sampled_logs_path}")

        # --- 【关键修改】生成带有 Context 信息的字符串 ---
        formatted_logs = []
        for log in final_samples:
            key = log['LogContent']
            # 获取对应的 tag，如果没有则默认为 Fallback
            tag = sample_annotations.get(key, "STRATEGY_FALLBACK")
            formatted_logs.append(self._format_log_for_llm(log, tag))

        return "\n".join(formatted_logs)

    def run(self, logs: List[Dict[str, Any]], force_regenerate: bool = False) -> Tuple[List[List[int]], Dict[int, int]]:
        """
        Executes the full 4-stage meta-programming and event clustering process.
        """
        logging.info(f"Starting Meta-Programmed Detection for dataset: {self.config.dataset}")
        
        processor_path = self.config.event_processor_path

        if force_regenerate or not os.path.exists(processor_path):
            logging.info("--- 🚀 Generation Phase Started ---")
            
            # Stage 1: Sample logs
            samples_str = self._generate_and_save_sample(logs)
            if not samples_str:
                logging.error("Aborting: Sample generation failed.")
                return [], {}

            # --- NEW: 加载采样日志数据用于 Phase I 的动态验证 ---
            validation_samples = []
            try:
                if os.path.exists(self.config.sampled_logs_path):
                    with open(self.config.sampled_logs_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            validation_samples.append(json.loads(line))
                logging.info(f"Loaded {len(validation_samples)} samples for runtime validation.")
            except Exception as e:
                logging.warning(f"Failed to load samples for validation: {e}. Validation will be static-only.")
                validation_samples = []

            # Stage 2: Discover Natural Language Rules
            logging.info("--- Stage 2: Discovering orthogonal natural language rules... ---")

            dataset_name = self.config.dataset
            guidance = DATASET_GUIDANCE.get(dataset_name, "")
            if not guidance:
                raise ValueError(f"No dataset guidance found for dataset '{dataset_name}'. Aborting.")
                
            nl_rules_prompt = PROMPT_FOR_NL_RULES.format(
                log_samples_string=samples_str,
                dataset_context=guidance["context"],
                dataset_specific_examples=guidance["examples"],
            )
            response_str = call_llm_api(self.client, nl_rules_prompt, self.config.llm_model_name, self.config)
            
            try:
                nl_rules = json.loads(response_str)
                with open(self.config.nl_rules_path, 'w', encoding='utf-8') as f:
                    json.dump(nl_rules, f, indent=2, ensure_ascii=False)
                logging.info(f"  -> ✅ Saved {len(nl_rules)} NL rules to {self.config.nl_rules_path}")
            except Exception as e:
                logging.error(f"Aborting: Failed to parse or save NL rules: {e}\nRaw response: {response_str}")
                return [], {}
            
            # --- Stage 3: Modified call to include validation_samples ---
            rule_functions_code = code_generator.generate_rule_functions(
                self.client, 
                self.config, 
                nl_rules, 
                validation_samples=validation_samples  # <--- PASS SAMPLES HERE
            )
            
            if not rule_functions_code:
                return [], {}

            framework_code = code_generator.generate_main_framework(self.client, self.config, rule_functions_code, nl_rules)
            if not framework_code:
                return [], {}

            code_generator.assemble_full_processor_file(self.config, rule_functions_code, framework_code)
        
        else:
            logging.info(f"--- ⏩ Skipping Generation Phase (using cached processor at {processor_path}) ---")

        # Application Phase
        logging.info("--- 🏁 Application Phase Started ---")
        try:
            return code_generator.apply_and_cluster_events(logs, processor_path)
        except Exception as e:
            logging.error(f"Application of generated processor failed: {e}", exc_info=True)
            return [], {}

################################################################################
# --- MAIN EXECUTION BLOCK FOR TESTING ---
################################################################################

if __name__ == '__main__':    
    config = Config()
    logging.info("--- Test Run Initializing ---")
    client = initialize_llm_client(config)

    if not client:
        logging.error("Exiting: LLM client could not be initialized. Check API keys in config.")
        exit()

    # 3. Create mock log data for testing
    # This data simulates a brute-force attack followed by a successful login.
    mock_logs = [
        {'Timestamp': datetime(2023, 1, 1, 10, 0, 0), 'PID': 101, 'ip': '192.168.1.10', 'EventTemplate': 'sshd: Failed password for invalid user admin', 'LogContent': '...'},
        {'Timestamp': datetime(2023, 1, 1, 10, 0, 1), 'PID': 101, 'ip': '192.168.1.10', 'EventTemplate': 'sshd: Failed password for root', 'LogContent': '...'},
        {'Timestamp': datetime(2023, 1, 1, 10, 0, 2), 'PID': 101, 'ip': '192.168.1.10', 'EventTemplate': 'sshd: Failed password for root', 'LogContent': '...'},
        {'Timestamp': datetime(2023, 1, 1, 10, 0, 3), 'PID': 101, 'ip': '192.168.1.10', 'EventTemplate': 'sshd: Failed password for root', 'LogContent': '...'},
        {'Timestamp': datetime(2023, 1, 1, 10, 0, 5), 'PID': 101, 'ip': '192.168.1.10', 'EventTemplate': 'sshd: Accepted password for root', 'LogContent': '...'},
        {'Timestamp': datetime(2023, 1, 1, 10, 0, 6), 'PID': 102, 'ip': '192.168.1.10', 'EventTemplate': 'sshd: session opened for user root by (uid=0)', 'LogContent': '...'},
        {'Timestamp': datetime(2023, 1, 1, 10, 5, 0), 'PID': 102, 'ip': '192.168.1.10', 'EventTemplate': 'sshd: session closed for user root', 'LogContent': '...'},
        {'Timestamp': datetime(2023, 1, 1, 11, 0, 0), 'PID': 205, 'ip': '10.0.0.5', 'EventTemplate': 'kernel: TCP: request_sock_TCP: Possible SYN flooding', 'LogContent': '...'},
    ]
    logging.info(f"Created {len(mock_logs)} mock logs for the test run.")

    # 4. Create and run the detector
    detector = MetaProgrammedDetector(config, client)
    
    # Use force_regenerate=True to ensure the entire generation pipeline runs every time for this test.
    # In production, you might set this to False to use cached processors.
    final_events, final_map = detector.run(mock_logs, force_regenerate=False)

    # 5. Print the final results
    print("\n" + "="*30 + " FINAL RESULTS " + "="*30)
    if final_events:
        print(f"\n✅ Detected {len(final_events)} events.")
        print("\nLog to Event Mapping:")
        print(json.dumps(final_map, indent=2))
        print("\nEvents (grouped log indices):")
        print(json.dumps(final_events, indent=2))
    else:
        print("\n❌ No events were detected or an error occurred during the process.")
    print("\n" + "="*75)

    