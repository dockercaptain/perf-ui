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
    "size": 0,  # We only want aggregation results
    "query": {
        "terms": {
            "status_code": [401, 403]
        }
    },
    "aggs": {
        "by_minute": {
            "date_histogram": {
                "field": "timestamp",  # Use .keyword for exact match
                "interval": "minute",
            }
        }
    }
}

resp = client.search(index=index_name, body=query)

for re in resp["aggregations"]["by_minute"]["buckets"]:
    print(re)

# print(len(resp["hits"]["hits"]))
# print("##########")