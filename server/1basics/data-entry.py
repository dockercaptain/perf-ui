import json
import random
from datetime import datetime, timedelta

# Sample pools
hosts = ['web-01', 'web-02', 'web-03', 'api-01', 'api-02', 'api-03']
levels = ['INFO', 'WARN', 'ERROR']
messages = [
    "Unauthorized access attempt detected from IP {ip}",
    "Access denied for user '{user}' on {path}",
    "Invalid credentials provided by user '{user}'",
    "Unathorised acess attemp from IP {ip}",
    "Access denied: IP {ip} attempted to reach {path}"
]
status_codes = [200, 401, 403]
users = ['admin', 'guest', 'devops', 'root', 'unknown']
paths = ['/admin/login', '/secure/data', '/api/auth', '/config/settings', '/api/token']
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'curl/7.68.0',
    'PostmanRuntime/7.32.0',
    'Python-urllib/3.9',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
]
geo_data = [
    {"country": "US", "city": "New York", "asn": 15169},
    {"country": "IN", "city": "Mumbai", "asn": 24560},
    {"country": "GB", "city": "London", "asn": 5607},
    {"country": "RU", "city": "Moscow", "asn": 12389},
    {"country": "IN", "city": "Delhi", "asn": 55836},
    {"country": "US", "city": "San Francisco", "asn": 13335}
]

# Tight IP pool for repetition
ip_pool = [
    "192.168.1.10",
    "10.0.0.5",
    "172.16.0.3",
    "203.0.113.45",
    "132.94.240.233",
    "175.81.3.97",
    "53.208.95.40"
]

# Generate one log entry
def generate_log_entry(index, base_time):
    ip = random.choice(ip_pool)
    user = random.choice(users)
    path = random.choice(paths)
    geo = random.choice(geo_data)
    status_code = random.choice(status_codes)
    host = random.choice(hosts)
    level = random.choice(levels)
    user_agent = random.choice(user_agents)
    method = random.choice(['GET', 'POST'])
    response_time = random.randint(100, 500)
    session_id = f"sess-{index:06d}"
    referrer = f"https://example.com{path}"
    timestamp = (base_time + timedelta(seconds=index)).isoformat() + "Z"

    # Format message with correct placeholders
    msg_template = random.choice(messages)
    message = msg_template.format(ip=ip, user=user, path=path)

    # Add key_values field
    key_values = {
        "ip": ip,
        "status_code": status_code,
        "user": user,
        "path": path,
        "geo_country": geo["country"],
        "geo_city": geo["city"],
        "asn": geo["asn"]
    }

    return {
        "timestamp": timestamp,
        "host": host,
        "level": level,
        "message": message,
        "status_code": status_code,
        "user": user,
        "path": path,
        "ip": ip,
        "user_agent": user_agent,
        "method": method,
        "geo": geo,
        "response_time_ms": response_time,
        "referrer": referrer,
        "session_id": session_id,
        "key_values": key_values
    }

# Generate and save to JSONL
def generate_logs_to_file(filename, count):
    base_time = datetime(2025, 9, 26, 10, 0, 0)
    with open(filename, 'w') as f:
        for i in range(count):
            log = generate_log_entry(i, base_time)
            f.write(json.dumps(log) + '\n')

# Run the generator
generate_logs_to_file('ids_logs.jsonl', 100000)
