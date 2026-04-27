# Generated Processors

This directory contains the outputs of **Phase I: Agent-Driven Logic Synthesis** of the LogNexus framework. Each subdirectory corresponds to one experimental run on a specific log dataset and stores all artifacts produced by the three-step offline pipeline: diversity-driven contextual sampling, hierarchical rule reasoning, and verified code synthesis.

---

## Directory Structure

```
generated_processors/
│
├── {Dataset}_{Run}/                  # One directory per experimental run
│   ├── sampled_logs.jsonl            # Diversity-driven sample set (Stage 1 output)
│   ├── natural_language_rules.json   # Inferred hierarchical partitioning rules (Stage 2 output)
│   ├── processor_{Dataset}.py        # Verified executable processor (Stage 3 output)
│   ├── rule_functions/               # Decomposed stateless key extractor functions
│   │   └── rule_{N}_{description}.py
│   ├── ablation_results/             # Per-run evaluation metrics (ARI, NMI, etc.)
│   │   └── final_summary.csv
│   └── ablation_weights/             # Pretrained Bi-Mamba and Transformer encoder weights
│       ├── uni_mamba_{Dataset}.pth
│       └── transformer_{Dataset}.pth
│
├── {Dataset}_mode_wise_statistics.csv  # Aggregated statistics across all runs for a dataset
└── eval.py                             # Evaluation script for computing clustering metrics
```

Datasets currently covered: **OpenSSH**, **Apache**, **Linux**.

---

## Phase I Concepts and Corresponding Files

### 1. Diversity-Driven Contextual Sampling

**Paper reference:** §3.1 (*Diversity-Driven Contextual Sampling*, Algorithm 1).

The sampling algorithm partitions the raw log stream into temporal clusters, scores each cluster by size, template entropy, and parameter variability (Eq. 1), and selects a compact but representative subset through three stages: mandatory template coverage, novelty-aware contextual deepening, and budget completion.

**Example file:** [`OpenSSH_01/sampled_logs.jsonl`](OpenSSH_01/sampled_logs.jsonl)

Each line in `sampled_logs.jsonl` is a JSON object representing one sampled log entry, enriched with parsed fields (`EventTemplate`, `TemplateID`, `Parameters`, `ProcessName`, `PID`, and extracted attribute fields such as `ip` and `rhost`). This structured representation is passed to the LLM as the input context for rule inference.

---

### 2. Hierarchical Rule Reasoning

**Paper reference:** §3.2 (*Hierarchical Rule Reasoning and Code Generation*).

Given the sampled contexts, the LLM infers partitioning logic organized as a hierarchy of two rule classes:

- **Mandatory rules** encode strict equivalence relations based on explicit identifiers (e.g., `PID`). These groupings are absolute and must never be split.
- **Heuristic rules** capture weaker but useful correlations through shared attributes (e.g., source IP, `rhost`) and temporal proximity. Common heuristic types include:
  - **MERGE EVENT CORES** rules — merge Event Cores from the same actor within a time window (e.g., brute-force campaigns, service restart sequences).
  - **KEY DIMENSION SPLIT** rules — force a new event when a key attribute (e.g., source IP) changes, so that logs from distinct actors are never conflated.
  - **BOUNDARY** rules — enforce hard event boundaries on state transitions (e.g., successful login, session close).
  - **STATE TRANSITION BOUNDARY** rules — delimit complete events by paired state markers (e.g., `session opened` / `session closed`).
  - **TIME-BASED BOUNDARY** rules — terminate an event when inactivity exceeds a threshold, preventing the conflation of temporally separate activity waves.

**Example files:**

| Dataset | Natural-language rules |
|---------|------------------------|
| OpenSSH | [`OpenSSH_01/natural_language_rules.json`](OpenSSH_01/natural_language_rules.json) |
| Apache  | [`Apache_01/natural_language_rules.json`](Apache_01/natural_language_rules.json) |
| Linux   | [`Linux_01/natural_language_rules.json`](Linux_01/natural_language_rules.json) |

The JSON schema contains two top-level keys: `mandatory_rules` (list of strings) and `heuristic_rules` (list of strings). Each string is a natural-language description of one inferred rule, written in the constrained vocabulary used during the synthesis prompt.

---

### 3. Verified Code Synthesis

**Paper reference:** §3.2 (*Hierarchical Rule Reasoning and Code Generation*).

The natural-language rules are synthesized into two complementary executable components:

#### 3a. Stateless Key Extractor Functions

Each rule is compiled into a standalone Python function that maps a single log entry (represented as a dictionary) to a list of grouping keys. Functions are stateless by design: they inspect only the fields of the current log entry and return typed key strings (e.g., `PID_24868`, `IP_183.62.140.253`). Mandatory rules produce identifier-based keys; heuristic rules may also produce composite or typed keys (e.g., `IP_TEMPLATE_…`, `MALFORMED_PACKET_IP_…`) to encode richer grouping semantics.

**Example files:** [`OpenSSH_01/rule_functions/`](OpenSSH_01/rule_functions/)

Each file in `rule_functions/` contains exactly one extractor function named after the rule it implements. The file name is a truncated, snake-cased version of the rule description, prefixed with `rule_{N}_`.

| Rule file | Implemented concept |
|-----------|---------------------|
| `rule_1_group_all_logs_that_share_the_exact_same_process_i.py` | Mandatory PID-based Event Core grouping |
| `rule_2_if_a_unique_highcardinality_session_or_transaction.py` | High-cardinality session/transaction identifier extraction |
| `rule_3_merge_event_cores_rule_for_ssh_bruteforcescanning_.py` | MERGE CORES: SSH brute-force/scanning by source IP |
| `rule_4_key_dimension_split_rule_even_if_logs_are_temporal.py` | KEY DIMENSION SPLIT: separate events by distinct source IP |
| `rule_5_boundary_rule_by_state_change__success_an_event_co.py` | BOUNDARY: successful SSH login initiates a new event |
| `rule_6_state_transition_boundary_rule__session_end_an_eve.py` | STATE TRANSITION BOUNDARY: session-close log ends the session event |
| `rule_7_merge__classify_rule_for_lockout_an_event_core_con.py` | MERGE & CLASSIFY: SSH lockout event reconstruction |
| `rule_8_merge__classify_rule_for_connection_errors_an_even.py` | MERGE & CLASSIFY: malformed packet and abrupt disconnect events |
| `rule_9_merge__classify_rule_for_dns_mismatch_an_event_cor.py` | MERGE & CLASSIFY: SSH DNS mismatch warning event |
| `rule_10_timebased_boundary_rule__inactivity_timeout_when_m.py` | TIME-BASED BOUNDARY: inactivity timeout (handled by orchestrator) |

#### 3b. Stateful Orchestrator (Disjoint-Set Union)

The synthesized key extractors are assembled into a single executable processor script. The orchestrator applies all extractor functions to each log entry in the stream and uses a **disjoint-set union (DSU)** structure to merge log entries that share at least one grouping key. Executing the processor on the full log stream yields the initial set of **coarse candidate partitions** passed to Phase II for refinement.

**Example file:** [`OpenSSH_01/processor_OpenSSH.py`](OpenSSH_01/processor_OpenSSH.py)

The processor is self-contained: it re-embeds all extractor functions and contains the DSU orchestrator in a single file, so it can be run independently on any preprocessed log stream without external dependencies beyond the Python standard library.

> **Note:** These files are auto-generated by the Agent-Driven Logic Synthesis pipeline and are not intended to be edited manually.

---

### 4. Synthesis Verification

**Paper reference:** §3.2 (*Hierarchical Rule Reasoning and Code Generation*).

Before the processor is accepted, two verification steps are applied:

1. **Static AST analysis** — an abstract syntax tree checker validates that only whitelisted standard-library modules (e.g., `re`, `datetime`) are imported and that no file I/O, network, or system-level operations are present.
2. **Sandbox execution** — the synthesized functions are executed on the Phase I sample set (`sampled_logs.jsonl`) to detect runtime failures, infinite loops, or pathologically slow regular expressions. If verification fails, the error trace is returned to the LLM for self-correction.

Only processors that pass both checks are committed to this directory.

---

### 5. Evaluation Artifacts

**Paper reference:** §4 (*Experiments*).

Each run directory contains an `ablation_results/final_summary.csv` file that records clustering quality metrics evaluated against ground-truth event labels:

| Column | Description |
|--------|-------------|
| `Mode` | Encoder backbone used (`uni_mamba`, `transformer`, etc.) |
| `Inference Time (ms)` | End-to-end inference latency |
| `MLM Acc` | Masked Log Modeling accuracy (pre-training task) |
| `RPD Acc` | Replaced Parameter Detection accuracy (pre-training task) |
| `ECO Acc` | Event Coherence Ordering accuracy (pre-training task) |
| `Adjusted Rand Index (ARI)` | Clustering agreement with ground truth |
| `Normalized Mutual Info (NMI)` | Normalized information overlap with ground truth |
| `Homogeneity` | Each predicted cluster contains only members of a single true event |
| `Completeness` | All members of a true event are in the same predicted cluster |
| `V-Measure` | Harmonic mean of Homogeneity and Completeness |
| `Predicted Event Count` | Number of events reconstructed by the framework |
| `True Event Count` | Number of ground-truth events in the dataset |

The `{Dataset}_mode_wise_statistics.csv` files at the top level aggregate these metrics across all five runs for each dataset (mean ± standard deviation).

Pretrained encoder weights used during ablation are stored in `ablation_weights/` as `.pth` files compatible with the Bi-Mamba and Transformer encoder architectures described in §3.3.

---

## Relation to the Full LogNexus Pipeline

```
Phase I  (this directory)
  sampled_logs.jsonl          ← Diversity-Driven Contextual Sampling
  natural_language_rules.json ← Hierarchical Rule Reasoning
  processor_{Dataset}.py      ── Coarse Candidate Partitions ──►  Phase II (event_refinement/)
                                                                    Bi-Mamba Encoder &
                                                                    Cascaded Event Refinement
                                                                       │
                                                                       ▼
                                                                   Phase III (knowledge_base/)
                                                                    Security Knowledge Base
                                                                    Construction
```

Phase II consumes the coarse candidate partitions produced by `processor_{Dataset}.py` and refines them into semantically coherent events using the Bi-Mamba encoder and the three-stage cascaded refinement procedure (attribute-rule-based splitting → model-based semantic splitting → content-aware fragment fusion). Phase III then organizes the refined events into the Security Knowledge Base through online clustering and LLM-driven knowledge generation.
