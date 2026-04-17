from opensearchpy import OpenSearch
import time
import json
import requests

# Step 1: Connect to OpenSearch

client = OpenSearch(hosts=[{'host': '192.168.1.150', 'port': 9200}])

index_name = "openapi-spec"
 
# Step 2: Fetch Swagger Spec

swagger_url = "http://localhost:8081/swagger/swagger.json"
response = requests.get(swagger_url)
paths = response.json()["paths"] 
docs = []
id = 1
for key in paths:
    paths[key]["path"] = key
    docs.append(paths[key])

print(docs)
for doc in docs:
    print("#######")
    # print(doc)
    client.create(index="apipaths", body=doc, id=id)
    id+=1
