from opensearchpy import OpenSearch
import json


client = OpenSearch(host="192.168.1.150", port="9200")
index_name = "logs"

# Path to your JSONL file
file_path = 'ids_logs.jsonl'

# Read and parse each line into a list of dictionaries
with open(file_path, 'r') as f:
    log_entries = [json.loads(line) for line in f]



id=1
for doc in log_entries:
    client.create(index=index_name, body=doc, id=id)
    id+=1

# Preview the first entry

# client.indices.delete(index=index_name)
# # if not client.indices.exists(index=index_name):
# #     client.indices.create(index=index_name)



# query = {
#     "_source": ["path", "status_code","ip"],
#     "query": {
#         "bool": {
#             "must": [
#                 {
#                     "terms": {"status_code": [401,403]},
#                 }
#             ]
#         }
#     },
# }

# resp = client.search(index=index_name, body=query)
# for res in resp["hits"]["hits"]:
#     print(res["_source"])
