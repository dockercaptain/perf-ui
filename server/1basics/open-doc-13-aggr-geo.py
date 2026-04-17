from opensearchpy import OpenSearch
import json


client = OpenSearch(host="192.168.1.150", port="9200")
index_name = "logs"

# Path to your JSONL file
file_path = "ids_logs.jsonl"

# Read and parse each line into a list of dictionaries
with open(file_path, "r") as f:
    log_entries = [json.loads(line) for line in f]

query = {
    "size": 0,
    "query": {"terms": {"status_code": [401, 403]}},
    "aggs": {
        "by_country": {
            "terms": {"field": "geo.country.keyword", "size": 10},
            "aggs": {
                "by_minute": {
                    "date_histogram": {
                        "field": "timestamp",
                        "interval": "minute",
                        "format": "yyyy-MM-dd HH:mm",
                    }
                }
            },
        }
    },
}


resp = client.search(index=index_name, body=query)

for res in resp["aggregations"]["by_country"]["buckets"]:
    for new in res["by_minute"]["buckets"]:
        print(new)

# print(len(resp["hits"]["hits"]))
# print("##########")
