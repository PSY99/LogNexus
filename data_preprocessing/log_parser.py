# -*- coding: utf-8 -*-
# /data_preprocessing/log_parser.py
import re
import logging
from datetime import datetime
import pandas as pd
from urlextract import URLExtract

def _parse_timestamp(ts_match_dict: dict, year_context: dict) -> datetime | None:
 """
 According topositivethenMatchDictionaryParseTimestamp.
 """
 ts_bracketed = ts_match_dict.get('ts_bracketed')
 ts_bare = ts_match_dict.get('ts_bare')

 if ts_bracketed:
 ts_str = ts_bracketed
 try:
 return datetime.strptime(ts_str, "%a %b %d %H:%M:%S %Y")
 except Valueerror:
 try:
 return datetime.strptime(ts_str, "%b %d %H:%M:%S %Y")
 except Valueerror:
 return None
 elif ts_bare:
 ts_str = ts_bare
 try:
 current_month = datetime.strptime(ts_str, "%b %d %H:%M:%S").month
 if year_context.get('prev_month') == 12 and current_month == 1:
 year_context['prev_year'] += 1
 year_context['prev_month'] = current_month
 year = year_context.get('prev_year', datetime.now().year)
 return datetime.strptime(f"{year} {ts_str}", "%Y %b %d %H:%M:%S")
 except Valueerror:
 return None
 return None

def template_to_regex(tmpl: str) -> str:
 r"""willLog templateConvertaspositivethentable."""
 pieces = tmpl.split("<*>")
 regex = "^"
 for i, p in enumerate(pieces):
 esc = re.escape(p).replace(r"\ ", r"\s+")
 regex += esc
 if i != len(pieces) - 1:
 regex += r"(.*?)"
 regex += "$"
 return regex

class TemplateMatcher:
 def __init__(self, csv_path, column="EventTemplate"):
 df = pd.read_csv(csv_path)
 templates = df[column].astype(str).tolist()
 self.template_to_id = {tmpl: i for i, tmpl in enumerate(templates)}
 self.compiled = [(tmpl, re.compile(template_to_regex(tmpl))) for tmpl in templates]
 
 def match_line(self, line: str) -> tuple[str, int, list]:
 """
 【fix】ReturnParameter list,Parseuse.
 """
 for tmpl, rgx in self.compiled:
 match = rgx.match(line)
 if match:
 template_id = self.template_to_id[tmpl]
 params = list(match.groups())
 params = [s for s in params if s != ""]
 return tmpl, template_id, params
 raise Valueerror(f"Line does not match any template: {line}")

class LogParser:
 """
 oneallLogParseLogic.
 assameDatasetextractParse.
 """
 # --- willallpositivethentabletemplateasproperty ---
 LOG_PARSING_PATTERN = re.compile(
 # 1. Timestamp (Timestamp) - supporthold
 r"^(?:\[(?P<ts_bracketed>[^]]+)]|(?P<ts_bare>\w{3}\s{1,2}\d{1,2}\s\d{2}:\d{2}:\d{2}))"
 # 2. name (Hostname) - Match
 r"\s+\S+\s+"
 # 3. name (process Name) - 【coregroup】
 # abilityMatch 'bluetooth' and 'sshd(pam_unix)' This wayrestoreName
 r"(?P<process_name>[a-zA-Z0-9_().\-/]+)"
 # 4. 【fix】newoneOptionalversionsplit.
 # isonegroup (?:...),MatchoneNullbackwardNumber、、grouptogether.
 # Match " 1.4.1" or " 2.8p1" .backward '?' Optional.
 r"(?:\s+[\w.-]+)?"
 # 4. OptionalPID - MatchinsideNumber
 r"(?:\[(?P<pid>\d+)])?"
 # 5. split (andNull)
 r":\s*"
 # 6. Message (Message Body) - content
 r"(?P<message>.*)$"
 )

 APACHE_PATTERN = re.compile(
 # 【fixpositive】Use \[ and \] Match
 r"^\[(?P<ts_bracketed>[^]]+)\]\s+"
 # 【fixpositive】Use \[ and \] Match
 r"\[(?P<level>[^]]+)\]\s+"
 r"(?P<message>.*)$"
 )
 APACHE_PID_PATTERN = re.compile(r'child (\d+)')

 IP_PATTERN = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')

 BGL_PATTERN = re.compile(
 r"^(?:(?P<label>\S+)\s+)?(?P<unix_ts>\d+)\s+"
 r"(?P<date>\d{4}\.\d{2}\.\d{2})\s+"
 r"(?P<location>\S+)\s+"
 r"(?P<detail_ts>\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+)\s+"
 r"(?P<component>\S+)\s+"
 r"(?P<category>\S+)\s+"
 r"(?P<subsystem>\S+)\s+"
 r"(?P<level>\S+)\s+"
 r"(?P<message>.*)$"
 )

 HADOOP_PATTERN = re.compile(
 r"^(?P<ts_date>\d{4}-\d{2}-\d{2})\s+(?P<ts_time>\d{2}:\d{2}:\d{2}),(?P<ts_ms>\d{3})\s+"
 r"(?P<level>\S+)\s+"
 r"\[(?P<component>[^\]]+)\]\s+" # Robustly capture anything in brackets
 r"(?P<class>[\w\.$]+):\s+"
 r"(?P<message>.*)$"
 )
 HADOOP_TASK_ATTEMPT_ID_PATTERN = re.compile(r'(attempt_(\d+_\d+)_([mr])_(\d+)_(\d+))')
 HADOOP_TASK_ID_PATTERN = re.compile(r'(task_(\d+_\d+)_([mr])_(\d+))')
 HADOOP_JVM_ID_PATTERN = re.compile(r'(jvm_(\d+_\d+)_([mr])_(\d+))')
 HADOOP_CONTAINER_ID_PATTERN = re.compile(r'(container(?:_e\d+)?_(\d+_\d+)_\d+_\d+)')
 HADOOP_APP_ATTEMPT_ID_PATTERN = re.compile(r'(appattempt_(\d+_\d+)_(\d+))')
 HADOOP_JOB_ID_PATTERN = re.compile(r'(job_(\d+_\d+))')
 HADOOP_APP_ID_PATTERN = re.compile(r'(application_(\d+_\d+))')
 HADOOP_STRUCTURED_APP_ID_PATTERN = re.compile(r'application_id\s*{\s*id:\s*(\d+)\s*cluster_timestamp:\s*(\d+)\s*}')

 HDFS_PATTERN = re.compile(
 # 1. Timestamp: 081109 203518
 r"^(?P<ts_date>\d{6})\s+(?P<ts_time>\d{6})\s+"
 # 2. PID/ID: 143
 r"(?P<pid>\d+)\s+"
 # 3. LogLevel: INFO
 r"(?P<level>\S+)\s+"
 # 4. Component/Java: dfs.DataNode$DataXceiver
 r"(?P<component>[\w$.]+):\s+"
 # 5. Message
 r"(?P<message>.*)$"
 )
 HDFS_BLOCK_ID_PATTERN = re.compile(r'(blk_[-]?\d+)')
 HDFS_PIPELINE_PATTERN = re.compile(r'pipeline\s+([^:]+:\d+(?:,\s*[^:]+:\d+)*)')

 ### ZOOKEEPER ADDITIONS START ###
 ZOOKEEPER_PATTERN = re.compile(
 # Timestamp: 2015-08-21 15:55:10,767
 r"^(?P<ts_date>\d{4}-\d{2}-\d{2})\s+(?P<ts_time>\d{2}:\d{2}:\d{2}),(?P<ts_ms>\d{3})\s+-\s+"
 # Level: INFO
 r"(?P<level>\S+)\s+"
 # Thread info: [Commitprocessor:2:ZooKeeperServer@595]
 r"\[(?P<thread_info>[^\]]+)\]\s+-\s+"
 # Message Body
 r"(?P<message>.*)$"
 )
 ZOOKEEPER_SESSION_ID_PATTERN = re.compile(r'(0x[0-9a-fA-F]+)')
 ZOOKEEPER_CLIENT_IP_PORT_PATTERN = re.compile(r'/([\d.]+):(\d+)')
 ### ZOOKEEPER ADDITIONS END ###

 def __init__(self, template_matcher: TemplateMatcher):
 self.template_matcher = template_matcher
 self.url_extractor = URLExtract()

 def _extract_urls_from_params(self, params: list[str]) -> list[str]:
 all_urls = []
 if not params:
 return all_urls
 
 for param in params:
 if isinstance(param, str):
 # UseFindURL
 found_urls = self.url_extractor.find_urls(param)
 all_urls.extend(found_urls)
 
 return sorted(list(set(all_urls)))

 def _extract_ip_from_node_str(self, node_str: str) -> str | None:
 """
 fromoneString( '/10.250.19.102:54106' or '10.250.10.6:50010')inExtractIP.
 """
 if not node_str:
 return None
 # self.IP_PATTERN isweIPpositivethentable
 match = self.IP_PATTERN.search(node_str)
 # IffoundIP,Return,OtherwiseReturnNone
 return match.group(0) if match else None

 def _extract_ips_from_pipeline(self, pipeline_str: str) -> list[str]:
 """ Helper to extract all IPs from a HDFS pipeline string. """
 ips = []
 # Split by comma and process each node string
 for node in pipeline_str.split(','):
 ip = self._extract_ip_from_node_str(node.strip())
 if ip:
 ips.append(ip)
 return ips

 def _parse_hadoop(self, line: str):
 """
 A highly reliable, multi-stage parser for Hadoop ecosystem logs (YARN, MapReduce, HDFS).
 It performs hierarchical ID extraction and handles various formats found in the test set.
 """
 # 1. Base parsing for the log skeleton
 base_match = self.HADOOP_PATTERN.match(line)
 if not base_match:
 return None # Not a valid Hadoop log line
 
 gd = base_match.groupdict()
 try:
 timestamp = datetime.strptime(f"{gd['ts_date']} {gd['ts_time']},{gd['ts_ms']}", "%Y-%m-%d %H:%M:%S,%f")
 except (Valueerror, Typeerror, Keyerror):
 timestamp = None

 message_body = gd.get('message', '').strip()
 template, template_id, params = self.template_matcher.match_line(message_body)

 urls = self._extract_urls_from_params(params)

 # 2. initialize all potential structured fields
 application_id, job_id, app_attempt_id, task_id, task_attempt_id, container_id, jvm_id = [None] * 7
 block_ids, src_ips, dst_ips = [], [], []

 # 3. Hierarchical and Parallel ID Extraction
 # We search for all patterns and fill fields from most specific to most general.
 
 # --- Level 1: Most specific IDs ---
 task_attempt_match = self.HADOOP_TASK_ATTEMPT_ID_PATTERN.search(line)
 if task_attempt_match:
 task_attempt_id = task_attempt_match.group(1)
 # Derive parent IDs
 id_part = task_attempt_match.group(2)
 task_id = f"task_{id_part}_{task_attempt_match.group(3)}_{task_attempt_match.group(4)}"
 job_id = f"job_{id_part}"
 application_id = f"application_{id_part}"

 # --- Level 2: Task-level and Container-level IDs ---
 if not task_id: # Only search if not already found
 task_match = self.HADOOP_TASK_ID_PATTERN.search(line)
 if task_match:
 task_id = task_match.group(1)
 id_part = task_match.group(2)
 if not job_id: job_id = f"job_{id_part}"
 if not application_id: application_id = f"application_{id_part}"

 container_match = self.HADOOP_CONTAINER_ID_PATTERN.search(line)
 if container_match:
 container_id = container_match.group(1)
 id_part = container_match.group(2)
 if not application_id: application_id = f"application_{id_part}"

 if not jvm_id:
 jvm_match = self.HADOOP_JVM_ID_PATTERN.search(line)
 if jvm_match:
 jvm_id = jvm_match.group(1)
 id_part = jvm_match.group(2)
 if not job_id: job_id = f"job_{id_part}"
 if not application_id: application_id = f"application_{id_part}"

 # --- Level 3: Application-level IDs ---
 app_attempt_match = self.HADOOP_APP_ATTEMPT_ID_PATTERN.search(line)
 if app_attempt_match:
 app_attempt_id = app_attempt_match.group(1)
 id_part = app_attempt_match.group(2)
 if not application_id: application_id = f"application_{id_part}"

 if not job_id:
 job_match = self.HADOOP_JOB_ID_PATTERN.search(line)
 if job_match:
 job_id = job_match.group(1)
 id_part = job_match.group(2)
 if not application_id: application_id = f"application_{id_part}"
 
 if not application_id:
 app_match = self.HADOOP_APP_ID_PATTERN.search(line)
 if app_match:
 application_id = app_match.group(1)

 # --- Level 4: Special Formats (can override previous findings) ---
 structured_match = self.HADOOP_STRUCTURED_APP_ID_PATTERN.search(line)
 if structured_match:
 app_num_id = int(structured_match.group(1))
 cluster_ts = structured_match.group(2)
 # Reconstruct the standard ID, padding the app number to 4 digits
 reconstructed_id = f"application_{cluster_ts}_{app_num_id:04d}"
 application_id = reconstructed_id
 if not job_id:
 job_id = f"job_{cluster_ts}_{app_num_id:04d}"

 # 4. HDFS-specific entity extraction (if applicable)
 java_class = gd.get('class', '')
 if 'org.apache.hadoop.hdfs.DFSClient' in java_class:
 block_ids.extend(self.HDFS_BLOCK_ID_PATTERN.findall(line))
 
 pipeline_match = self.HDFS_PIPELINE_PATTERN.search(line)
 if pipeline_match:
 # Assuming the pipeline lists destination IPs
 dst_ips.extend(self._extract_ips_from_pipeline(pipeline_match.group(1)))
 
 # 5. General IP Extraction (for non-pipeline logs)
 # Avoid re-parsing IPs if already found in a pipeline
 if not src_ips and not dst_ips:
 all_ips = self.IP_PATTERN.findall(line)
 if all_ips:
 # A simple heuristic: assume the first IP is src, others are dst.
 # This can be refined if more context is available.
 src_ips.append(all_ips[0])
 if len(all_ips) > 1:
 dst_ips.extend(all_ips[1:])

 return {
 # Core Fields
 'Timestamp': timestamp,
 'LogContent': line,
 'EventTemplate': template,
 'TemplateID': template_id,
 'Parameters': params,
 
 # Hadoop Base Fields
 'Level': gd.get('level'),
 'Component': gd.get('component'),
 'JavaClass': java_class,
 
 # YARN Hierarchical IDs
 'application_id': application_id,
 'job_id': job_id,
 'app_attempt_id': app_attempt_id,
 'task_id': task_id,
 'task_attempt_id': task_attempt_id,
 'container_id': container_id,
 'jvm_id': jvm_id,

 # HDFS/Network Fields
 'block_ids': list(set(block_ids)), # Use set to remove duplicates
 'src_ips': list(set(src_ips)),
 'dst_ips': list(set(dst_ips)),
 'URLs': urls
 }

 def _parse_bgl(self, line: str):
 match = self.BGL_PATTERN.match(line)
 if not match: return None
 
 gd = match.groupdict()
 try:
 timestamp = datetime.fromtimestamp(int(gd['unix_ts']))
 except Exception:
 timestamp = None

 message_body = gd.get('message', '').strip()
 template, template_id, params = self.template_matcher.match_line(message_body)

 urls = self._extract_urls_from_params(params)

 return {
 'Timestamp': timestamp,
 'LogContent': line,
 'EventTemplate': template,
 'TemplateID': template_id,
 'Parameters': params,
 'Label': gd.get('label'),
 'Location': gd.get('location'),
 'Component': gd.get('component'),
 'Category': gd.get('category'),
 'Subsystem': gd.get('subsystem'),
 'Level': gd.get('level'),
 'URLs': urls,
 }

 def _parse_apache(self, line: str, year_context: dict, structured_info=None):
 match = self.APACHE_PATTERN.match(line)
 if not match:
 return None

 match_dict = match.groupdict()
 timestamp = _parse_timestamp(match_dict, year_context)
 if not timestamp:
 return None

 message_body = match_dict.get('message', '').strip()
 if structured_info is not None:
 template = structured_info['EventTemplate']
 template_id = self.template_matcher.template_to_id.get(template, -1)
 _, _, params = self.template_matcher.match_line(message_body)
 else:
 template, template_id, params = self.template_matcher.match_line(message_body)

 urls = self._extract_urls_from_params(params)

 # fromMessageinExtractPID
 pid = None
 pid_match = self.APACHE_PID_PATTERN.search(message_body)
 if pid_match:
 pid = int(pid_match.group(1))

 ip_match = self.IP_PATTERN.search(line)
 if ip_match and (ip_match.group(0) == "127.0.0.1" or ip_match.group(0) == "0.0.0.0"):
 ip_match = None

 return {
 'Timestamp': timestamp,
 'LogContent': line,
 'EventTemplate': template,
 'TemplateID': template_id,
 'Parameters': params,
 'Level': match_dict.get('level'),
 'PID': pid,
 'ip': ip_match.group(0) if ip_match else None,
 'URLs': urls,
 }

 def _parse_default(self, line: str, year_context: dict, structured_info=None):
 match = self.LOG_PARSING_PATTERN.match(line)
 if not match: 
 return None

 match_dict = match.groupdict()
 timestamp = _parse_timestamp(match_dict, year_context)
 if not timestamp:
 return None
 
 message_body = match_dict.get('message', '').strip()
 if structured_info is not None:
 template = structured_info['EventTemplate']
 template_id = self.template_matcher.template_to_id.get(template, -1)
 _, _, params = self.template_matcher.match_line(message_body)
 else:
 template, template_id, params = self.template_matcher.match_line(message_body)

 urls = self._extract_urls_from_params(params)

 process_name = match_dict.get('process_name')
 if process_name:
 params.insert(0, process_name.lower())

 ip_match = self.IP_PATTERN.search(line)
 if ip_match and (ip_match.group(0) == "127.0.0.1" or ip_match.group(0) == "0.0.0.0"):
 ip_match = None

 return {
 'Timestamp': timestamp,
 'LogContent': line,
 'EventTemplate': template,
 'TemplateID': template_id,
 'Parameters': params,
 'processName': process_name,
 'PID': int(match_dict['pid']) if match_dict.get('pid') else None,
 'ip': ip_match.group(0) if ip_match else None,
 'rhost': urls,
 }
 
 def _parse_hdfs(self, line: str, year_context: dict, structured_info=None):
 """
 【】
 asHDFSLog、based ontemplateboardlanguageintelligentabilityParse.
 """
 match = self.HDFS_PATTERN.match(line)
 if not match:
 return None

 gd = match.groupdict()
 
 try:
 ts_str = gd['ts_date'] + gd['ts_time']
 timestamp = datetime.strptime(ts_str, "%y%m%d%H%M%S")
 except (Valueerror, Keyerror):
 timestamp = None

 message_body = gd.get('message', '').strip()

 if structured_info is not None:
 template = structured_info['EventTemplate']
 template_id = self.template_matcher.template_to_id.get(template, -1)
 _, _, params = self.template_matcher.match_line(message_body)
 else:
 template, template_id, params = self.template_matcher.match_line(message_body)

 urls = self._extract_urls_from_params(params)

 # --- based ontemplateboardlanguageExtract ---
 src_ips, dst_ips = [], []
 block_id_match = self.HDFS_BLOCK_ID_PATTERN.search(message_body)
 block_id = block_id_match.group(1) if block_id_match else None
 
 # Rule1: Match "src:... dest:..." (E42, E39)
 if ' src: ' in message_body and ' dest: ' in message_body:
 src_match = re.search(r'src:\s*([^ ]+)', message_body)
 dst_match = re.search(r'dest:\s*([^ ]+)', message_body)
 if src_match:
 src_ips.append(self._extract_ip_from_node_str(src_match.group(1)))
 if dst_match:
 dst_ips.append(self._extract_ip_from_node_str(dst_match.group(1)))

 # Rule2: Match "local=... remote=..." (E4, E5, E2, E1Log)
 elif 'local=' in message_body and 'remote=' in message_body:
 local_match = re.search(r'local=(.*?)[,\]]', message_body)
 remote_match = re.search(r'remote=(.*?)[,\]]', message_body)
 if local_match:
 src_ips.append(self._extract_ip_from_node_str(local_match.group(1)))
 if remote_match:
 dst_ips.append(self._extract_ip_from_node_str(remote_match.group(1)))
 
 # Rule3: Match "from..." (E41)
 elif ' from ' in message_body and 'Received block' in message_body:
 from_match = re.search(r'from\s*([^ ]+)', message_body)
 if from_match:
 src_ips.append(self._extract_ip_from_node_str(from_match.group(1)))

 # Rule4: Match "to..." (E43, E45, E33, E32)
 elif ' to ' in message_body:
 # a: "Transmitted/Served block... to..." (E43, E45)
 match = re.search(r'block.*? to (.*)', message_body)
 if match:
 # IPusuallyinMessagebeginning, "10.250.14.224:50010:Transmitted..."
 src_part = message_body.split(':', 1)[0]
 if self.IP_PATTERN.match(src_part):
 src_ips.append(self._extract_ip_from_node_str(src_part))
 
 # markIPin "to" backward
 dst_nodes_str = match.group(1)
 # processmark, "to <ip1>, <ip2>" (E33)
 dst_nodes = [node.strip() for node in dst_nodes_str.replace(' and ',',').split(',')]
 dst_ips.extend([self._extract_ip_from_node_str(node) for node in dst_nodes])
 
 # b: "ask... to replicate... to datanode(s)..." (E32)
 match = re.search(r'ask (.*?) to replicate.* to datanode\(s\)\s*(.*)', message_body)
 if match:
 src_ips.append(self._extract_ip_from_node_str(match.group(1)))
 # markIPisNullsplitList
 dst_nodes = match.group(2).split()
 dst_ips.extend([self._extract_ip_from_node_str(node) for node in dst_nodes])

 # Rule5: Match "blockMap updated: <ip> is added to <blk>" (E22)
 elif 'blockMap updated' in message_body:
 match = re.search(r'updated:\s*([^ ]+)\s*is added to', message_body)
 if match:
 # inunderin,Addasis
 src_ips.append(self._extract_ip_from_node_str(match.group(1)))

 # backwardprepareRule: IfRuleMatch,thenExtractallIPasIP (info)
 if not src_ips and not dst_ips:
 all_ips = self.IP_PATTERN.findall(line)
 src_ips.extend(all_ips)

 job_id_match = self.HADOOP_JOB_ID_PATTERN.search(line)
 job_id = job_id_match.group(0) if job_id_match else None

 return {
 'Timestamp': timestamp,
 'LogContent': line,
 'EventTemplate': template,
 'TemplateID': template_id,
 'Parameters': params,
 'PID': int(gd['pid']) if gd.get('pid') else None,
 'Level': gd.get('level'),
 'Component': gd.get('component'),
 'block_id': block_id,
 # and,backwardReturn
 'src_ips': sorted(list(set(filter(None, src_ips)))),
 'dst_ips': sorted(list(set(filter(None, dst_ips)))),
 'job_id': job_id,
 'URLs': urls,
 }
 
 ### ZOOKEEPER_PARSE_METHOD START ###
 def _parse_zookeeper(self, line: str):
 """
 asZooKeeperLoguseParse.
 """
 # 1. UsetemplatelineParse
 base_match = self.ZOOKEEPER_PATTERN.match(line)
 if not base_match:
 return None
 
 gd = base_match.groupdict()
 
 # 2. ParseTimestamp
 try:
 timestamp = datetime.strptime(f"{gd['ts_date']} {gd['ts_time']},{gd['ts_ms']}", "%Y-%m-%d %H:%M:%S,%f")
 except (Valueerror, Typeerror, Keyerror):
 timestamp = None

 message_body = gd.get('message', '').strip()
 template, template_id, params = self.template_matcher.match_line(message_body)

 # 3. Parse/Componentinfo
 thread_info_str = gd.get('thread_info', '')
 thread_parts = thread_info_str.split(':')
 thread_name, java_class, line_number = None, None, None
 if len(thread_parts) > 1:
 class_part = thread_parts[-1]
 thread_name = ':'.join(thread_parts[:-1])
 if '@' in class_part:
 java_class, line_number = class_part.split('@', 1)
 line_number = int(line_number) if line_number.isdigit() else None
 else:
 java_class = class_part
 else:
 thread_name = thread_info_str

 # 4. fromMessageinExtractkeykey
 session_id_match = self.ZOOKEEPER_SESSION_ID_PATTERN.search(message_body)
 session_id = session_id_match.group(1) if session_id_match else None

 client_ip, client_port = None, None
 client_match = self.ZOOKEEPER_CLIENT_IP_PORT_PATTERN.search(message_body)
 if client_match:
 client_ip = client_match.group(1)
 client_port = int(client_match.group(2))

 return {
 # Core Fields
 'Timestamp': timestamp,
 'LogContent': line,
 'EventTemplate': template,
 'TemplateID': template_id,
 'Parameters': params,
 
 # ZooKeeper Base Fields
 'Level': gd.get('level'),
 'ThreadName': thread_name,
 'JavaClass': java_class,
 'LineNumber': line_number,
 
 # Extracted Entities
 'session_id': session_id,
 'client_ip': client_ip,
 'client_port': client_port,
 }
 ### ZOOKEEPER_PARSE_METHOD END ###

 def parse(self, line: str, dataset_type: str, year_context: dict, structured_info=None):
 """
 split,According toDatasetTypeCallParse.
 """
 if dataset_type == "Hadoop":
 return self._parse_hadoop(line)
 elif dataset_type == "BGL":
 return self._parse_bgl(line)
 elif dataset_type == "Apache":
 return self._parse_apache(line, year_context, structured_info)
 elif dataset_type in ["Linux", "OpenSSH"]:
 return self._parse_default(line, year_context, structured_info)
 elif dataset_type == "HDFS":
 return self._parse_hdfs(line, year_context, structured_info)
 elif dataset_type == "Zookeeper":
 return self._parse_zookeeper(line)
 else:
 logging.warning(f"No specific parser for dataset '{dataset_type}'. Using default.")
 return self._parse_default(line, year_context, structured_info)
 

