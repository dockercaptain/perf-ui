from opensearchpy import OpenSearch
import json
import requests

client = OpenSearch(hosts=[{'host': '192.168.1.150', 'port': 9200}])

url = "http://localhost:8081/swagger/swagger.json"
response = requests.get(url)
spec = response.json()

index_name = "openapi-spec"

if client.indices.exists(index=index_name):
    client.indices.create(index=index_name)

for path, methods in spec.get("paths", {}).items():
    for method, details in methods.items():
        doc = {
            "path": path,
            "method": method.upper(),
            "summary": details.get("summary", ""),
            "parameters": [p['name'] for p in details.get("parameters", [])],
            "responses": list(details.get("responses", {}).keys())
        }
        client.index(index="openapi-spec", body=doc)

