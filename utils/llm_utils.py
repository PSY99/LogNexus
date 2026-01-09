# utils/llm_utils.py

import os
import logging
import time
from typing import Optional, Any

from openai import OpenAI, RateLimitError, APIConnectionError

from .config import Config

def initialize_llm_client(config: Config) -> Optional[OpenAI]:
    """
    Initializes and returns the OpenAI client using v1.x.x syntax.
    """
    api_key = config.llm_api_key
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        logging.error("LLM API key is not configured. Please set it in utils/config.py or as an environment variable.")
        return None
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=config.llm_base_url,
            timeout=config.llm_api_timeout,
            max_retries=config.llm_api_retries,
        )
        client.models.list()
        logging.info("OpenAI client initialized and connection successful.")
        return client
    except Exception as e:
        logging.error(f"Failed to initialize OpenAI client: {e}")
        return None


def call_llm_api(
    client: OpenAI,
    prompt: str,
    model_name: str,
    config: Config,
    temperature: float = 0.0
) -> Optional[str]:
    """
    Calls the LLM API with a given prompt and handles retries, errors, and response cleaning.
    """
    for attempt in range(config.llm_api_retries):
        try:
            logging.info(f"Calling LLM API (Attempt {attempt + 1}/{config.llm_api_retries})...")
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                # extra_body={"enable_thinking": False}
            )
            
            content = response.choices[0].message.content.strip()
            
            # --- 【关键修复：智能代码块提取】 ---
            # 逻辑：寻找第一个 ``` 和最后一个 ```，提取中间的内容。
            # 这样即使开头有 "Here is the code:" 也能正确处理。
            
            start_marker = "```"
            end_marker = "```"
            
            # 1. 寻找第一个代码块标记的位置
            start_index = content.find(start_marker)
            
            if start_index != -1:
                # 2. 寻找最后一个代码块标记的位置 (从后往前找)
                end_index = content.rfind(end_marker)
                
                # 确保找到了结束标记，并且结束标记在开始标记之后
                if end_index != -1 and end_index > start_index:
                    # 3. 确定代码内容的开始位置
                    # 我们需要跳过 ```python 或 ```json 这一行
                    # 从 start_index 开始找第一个换行符
                    first_newline = content.find('\n', start_index)
                    
                    if first_newline != -1 and first_newline < end_index:
                        # 提取换行符之后，结束标记之前的内容
                        content = content[first_newline + 1 : end_index].strip()
                    else:
                        # 极端情况：只有一行代码且没有换行 (比较少见)
                        # 直接跳过 ``` (3个字符)
                        content = content[start_index + 3 : end_index].strip()
                else:
                    # 只有开始标记没有结束标记，可能是截断了，或者格式错误
                    # 这种情况下，通常保留 start_index 之后的所有内容比较安全
                    logging.warning("Found start code block but no end block. Extracting remaining text.")
                    content = content[start_index + 3:].strip()

            logging.info("LLM API call successful and response cleaned.")
            return content
        
        except RateLimitError as e:
            logging.warning(f"LLM API Rate Limit Exceeded: {e}. Retrying after a delay...")
            time.sleep(10 * (attempt + 1))
        
        except APIConnectionError as e:
            logging.warning(f"LLM API Connection Error: {e}. Retrying...")
            time.sleep(5)
            
        except Exception as e:
            logging.error(f"An unexpected error occurred when calling LLM API: {e}", exc_info=True)
            time.sleep(5)

    logging.error("LLM API call failed after all retries.")
    return None