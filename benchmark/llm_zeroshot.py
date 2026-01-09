# benchmark/llm_zeroshot.py

import json
import logging
import re
from typing import List, Dict, Any, Set, Tuple
from tqdm import tqdm

# 尝试导入项目工具函数
try:
    from utils.llm_utils import call_llm_api
    # 导入你精心设计的领域知识库
    from event_detector.event_detector import DATASET_GUIDANCE
except ImportError:
    call_llm_api = None
    DATASET_GUIDANCE = {}

# ================= PROMPT TEMPLATES =================

# 1. Naive Zero-shot
PROMPT_NAIVE = """
You are an expert system log analyst.
Your task is to group the following raw logs into logical "Event Sessions".

### Definition of an Event Session:
- An Event Session is a sequence of logs representing a single, atomic activity.
- Logs with the same identifiers (like PID, IP) or occurring closely in time usually belong to the same session.

### Input Logs (Format: RelativeID | Timestamp | Content):
{log_chunk}

### Output Requirement:
Return a JSON object containing a list of lists. Each inner list represents ONE session and contains the "RelativeID"s.
Example: {{ "sessions": [[0, 1], [2], [3, 4]] }}

**IMPORTANT**: Return ONLY the valid JSON string.
"""

# 2. Knowledge-Enhanced Zero-shot
PROMPT_KNOWLEDGE = """
You are an expert system log analyst specializing in {dataset_name} logs.
Your task is to group the following raw logs into logical "Event Sessions".

### Definition of an Event Session:
- An Event Session is a complete lifecycle of an activity (e.g., a full SSH login, a complete Hadoop job).
- It often spans **multiple** PIDs, Threads, or Components.

### Input Logs (Format: RelativeID | Timestamp | Content):
{log_chunk}

### Domain Knowledge (Context):
{domain_context}

### Grouping Guidelines (Reference Only):
The following rules describe how events are typically structured. 
**CRITICAL INSTRUCTION**: Do NOT stop at the "Event Core" level. You MUST aggressively apply the semantic merging logic to reconstruct the FULL session. If logs look like they belong to the same logical workflow (e.g., brute force attack from same IP), GROUP THEM, even if they have different PIDs.

{specific_rules}

### Output Requirement:
Return a JSON object containing a list of lists. Each inner list represents ONE session and contains the "RelativeID"s.
Example: {{ "sessions": [[0, 1], [2], [3, 4]] }}

**IMPORTANT**: Return ONLY the valid JSON string.
"""

# 3. Chain-of-Thought with Knowledge
PROMPT_COT_KNOWLEDGE = """
You are an expert system log analyst specializing in {dataset_name} logs.
Your task is to group the following raw logs into logical "Event Sessions".

### Definition of an Event Session:
- An Event Session is a sequence of logs representing a single, atomic activity.
- Logs with the same identifiers (like PID, IP) or occurring closely in time usually belong to the same session.

### Domain Knowledge for {dataset_name}:
{domain_context}

### Input Logs (Format: RelativeID | Timestamp | Content):
{log_chunk}

### Instructions:
1. **Analyze**: Scan logs for identifiers (PIDs, IPs) and time gaps.
2. **Reason**: Explain your grouping logic step-by-step.
3. **Group**: Group the RelativeIDs into sessions.
4. **Format**: Output the result in JSON format.

### Output Format:
First provide your reasoning, then provide the JSON block enclosed in markdown code tags.

Example:
Analysis: Log 0 and 2 share PID 1234.
```json
{{
  "sessions": [[0, 2], [1]]
}}
```
"""

# ================= HELPER CLASS: Union-Find =================
class UnionFind:
    """Helper class to merge sessions across sliding windows."""
    def __init__(self, size):
        self.parent = list(range(size))

    def find(self, i):
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j

    def get_groups(self):
        groups = {}
        for i in range(len(self.parent)):
            root = self.find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(i)
        return list(groups.values())

# ================= MAIN CLASS =================

class LLMBaseline:
    """
    Universal LLM Baseline supporting multiple strategies with Sliding Window.
    """
    def __init__(self, client: Any, config: Any, strategy: str = 'naive', chunk_size: int = 50, overlap: int = 10):
        self.client = client
        self.config = config
        self.strategy = strategy.lower()
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.dataset_name = getattr(config, 'dataset', 'Linux')
        
        self.dataset_info = DATASET_GUIDANCE.get(self.dataset_name, DATASET_GUIDANCE.get('Linux'))
        
        if call_llm_api is None:
            logging.error("LLMBaseline: Could not import 'call_llm_api'. Check python path.")

    def _format_rules_for_prompt(self) -> str:
        if not self.dataset_info:
            return ""
        try:
            rules_json = json.loads(self.dataset_info.get('examples', '{}').strip()[1:-1])
            mandatory = rules_json.get('mandatory_rules', [])
            heuristic = rules_json.get('heuristic_rules', [])
            text = "Mandatory Rules:\n" + "\n".join([f"- {r}" for r in mandatory])
            text += "\n\nHeuristic Rules:\n" + "\n".join([f"- {r}" for r in heuristic])
            return text
        except:
            return "Use standard log grouping logic."

    def _get_prompt(self, log_lines: List[str]) -> str:
        chunk_str = "\n".join(log_lines)
        
        if self.strategy == 'naive':
            return PROMPT_NAIVE.format(log_chunk=chunk_str)
        
        domain_context = self.dataset_info.get('context', '')
        specific_rules = self._format_rules_for_prompt()
        
        if self.strategy == 'cot':
            return PROMPT_COT_KNOWLEDGE.format(
                dataset_name=self.dataset_name,
                domain_context=domain_context,
                log_chunk=chunk_str
            )
        else: 
            return PROMPT_KNOWLEDGE.format(
                dataset_name=self.dataset_name,
                domain_context=domain_context,
                specific_rules=specific_rules,
                log_chunk=chunk_str
            )

    def _extract_json(self, response_str: str) -> Dict:
        """Robust JSON extraction."""
        try:
            return json.loads(response_str)
        except json.JSONDecodeError:
            pass
        
        match = re.search(r"```json(.*?)```", response_str, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # 尝试寻找最外层的大括号
        match = re.search(r"\{.*\}", response_str, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        
        raise ValueError("Could not extract valid JSON from response")

    def predict(self, logs: List[Dict]) -> List[List[int]]:
        total_logs = len(logs)
        logging.info(f"LLM Baseline ({self.strategy}): Predicting on {total_logs} logs (Chunk={self.chunk_size}, Overlap={self.overlap})...")
        
        if not logs:
            return []

        # 初始化并查集
        dsu = UnionFind(total_logs)
        
        # 计算步长，确保 overlap 有效
        step = max(1, self.chunk_size - self.overlap)
        
        # 计算总 chunk 数用于进度条
        num_chunks = (total_logs + step - 1) // step
        
        for i in tqdm(range(0, total_logs, step), desc=f"LLM ({self.strategy})", total=num_chunks):
            chunk_start_index = i
            chunk_end_index = min(i + self.chunk_size, total_logs)
            
            # 如果是最后一个残缺的 chunk 且完全包含在前一个 chunk 中（虽然 range 逻辑通常避免这种情况），跳过
            if i > 0 and chunk_end_index - chunk_start_index <= self.overlap:
                continue

            chunk_logs = logs[chunk_start_index : chunk_end_index]
            
            # Format logs
            log_lines = []
            for rel_idx, log in enumerate(chunk_logs):
                content = log.get('LogContent', '')[:200].replace('\n', ' ')
                ts = str(log.get('Timestamp', ''))
                extras = []
                if 'PID' in log: extras.append(f"PID={log['PID']}")
                if 'ip' in log: extras.append(f"IP={log['ip']}")
                extra_str = f" [{', '.join(extras)}]" if extras else ""
                log_lines.append(f"{rel_idx} | {ts} | {content}{extra_str}")
            
            prompt = self._get_prompt(log_lines)
            
            try:
                response_str = call_llm_api(self.client, prompt, self.config.llm_model_name, self.config)
                data = self._extract_json(response_str)
                chunk_sessions_rel = data.get("sessions", [])
                
                # 将 chunk 内的相对分组转换为全局连接关系
                for session in chunk_sessions_rel:
                    # 过滤无效索引
                    valid_indices = [idx for idx in session if isinstance(idx, int) and 0 <= idx < len(chunk_logs)]
                    
                    if len(valid_indices) > 1:
                        # 将同一组内的 ID 两两合并
                        # 例如 [0, 1, 2] -> union(0+start, 1+start), union(1+start, 2+start)
                        # 转换为绝对索引
                        abs_indices = [idx + chunk_start_index for idx in valid_indices]
                        for k in range(len(abs_indices) - 1):
                            dsu.union(abs_indices[k], abs_indices[k+1])
                            
            except Exception as e:
                logging.error(f"LLM ({self.strategy}) Error at chunk {chunk_start_index}: {e}")
                # 出错时不合并，保持独立（默认行为）

        # 从并查集获取最终分组
        final_sessions = dsu.get_groups()
        
        # 排序，保证输出确定性
        final_sessions.sort(key=lambda x: x[0] if x else 0)
        
        return final_sessions