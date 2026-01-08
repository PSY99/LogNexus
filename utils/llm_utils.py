# utils/llm_utils.py

import os
import logging
import time
from typing import Optional, Any

from openai import OpenAI, RateLimiterror, APIConnectionerror

from .config import Config

def initialize_llm_client(config: Config) -> Optional[OpenAI]:
 """
 initializes and returns the OpenAI client using v1.x.x syntax.
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
 
 # --- 【Key fix：Smart code block extraction】 ---
 # Logic：Find first ``` and last ```,Extractin betweencontent.
 # This wayeven ifbeginninghas "Here is the code:" can beprocessed correctly.
 
 start_marker = "```"
 end_marker = "```"
 
 # 1. Find firstcode blockmarkerposition
 start_index = content.find(start_marker)
 
 if start_index != -1:
 # 2. Find lastcode blockmarkerposition (search from end)
 end_index = content.rfind(end_marker)
 
 # Ensurefoundend marker,andend markerinstart markerafter
 if end_index != -1 and end_index > start_index:
 # 3. determinecodecontentstartposition
 # weneed toskip ```python or ```json this line
 # from start_index startfind firstnewline
 first_newline = content.find('\n', start_index)
 
 if first_newline != -1 and first_newline < end_index:
 # Extractnewlineafter,end markerbeforecontent
 content = content[first_newline + 1 : end_index].strip()
 else:
 # Edge case：only hasone linecodewith no换line (rare)
 # directlyskip ``` (3characters)
 content = content[start_index + 3 : end_index].strip()
 else:
 # only hasstart markerno endmarker,possiblytruncated,orformat error
 # in this case,usuallykeep start_index afterallcontentsafer
 logging.warning("Found start code block but no end block. Extracting remaining text.")
 content = content[start_index + 3:].strip()

 logging.info("LLM API call successful and response cleaned.")
 return content
 
 except RateLimiterror as e:
 logging.warning(f"LLM API Rate Limit Exceeded: {e}. Retrying after a delay...")
 time.sleep(10 * (attempt + 1))
 
 except APIConnectionerror as e:
 logging.warning(f"LLM API Connection error: {e}. Retrying...")
 time.sleep(5)
 
 except Exception as e:
 logging.error(f"An unexpected error occurred when calling LLM API: {e}", exc_info=True)
 time.sleep(5)

 logging.error("LLM API call failed after all retries.")
 return None