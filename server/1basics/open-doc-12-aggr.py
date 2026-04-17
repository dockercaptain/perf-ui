from opensearchpy import OpenSearch
import json


client = OpenSearch(host="192.168.1.150", port="9200")
index_name = "logs"

# Path to your JSONL file
file_path = 'ids_logs.jsonl'

# Read and parse each line into a list of dictionaries
with open(file_path, 'r') as f:
    log_entries = [json.loads(line) for line in f]

query = {
    "size": 10,  # We only want aggregation results
    "query": {
        "terms": {
            "status_code": [401, 403]
        }
    },
    "aggs": {
        "ip_hits": {
            "terms": {
                "field": "ip.keyword",  # Use .keyword for exact match
                "size": 100  # Adjust to show more IPs
            }
        }
    }
}

resp = client.search(index=index_name, body=query)

print(resp)
for re in resp["aggregations"]["ip_hits"]["buckets"]:
    print(re)

# print(len(resp["hits"]["hits"]))
# print("##########")