from opensearchpy import OpenSearch
import json
import os

# Step 1: Connect to OpenSearch
client = OpenSearch(hosts=[{'host': '192.168.1.150', 'port': 9200}])
index_name = "openapi-spec"

# Step 2: Define the endpoint to extract
target_path = "/ok"         # Change as needed
target_method = "GET"       # Change as needed

# Step 3: Query OpenSearch for the specific endpoint
query = {
    "query": {
        "bool": {
            "must": [
                {"term": {"path": target_path}},
                {"term": {"method": target_method}}
            ]
        }
    }
}

response = client.search(index=index_name, body=query, size=1)
hits = response.get("hits", {}).get("hits", [])

if not hits:
    print(f"No matching endpoint found for {target_method} {target_path}")
    exit()

doc = hits[0]["_source"]

# Step 4: Build minimal Swagger spec
swagger_spec = {
    "openapi": "3.0.0",
    "info": {
        "title": "Single Endpoint API",
        "version": "1.0.0"
    },
    "paths": {
        doc["path"]: {
            doc["method"].lower(): {
                "summary": doc.get("summary", ""),
                "description": doc.get("description", ""),
                "tags": doc.get("tags", []),
                "parameters": [
                    {
                        "name": param,
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"}
                    } for param in doc.get("request_parameter", [])
                ],
                "responses": {
                    code: {
                        "description": f"Response {code}"
                    } for code in doc.get("responses", [])
                }
            }
        }
    }
}

# Step 5: Save Swagger spec (optional)
with open("single-endpoint-swagger.json", "w") as f:
    json.dump(swagger_spec, f, indent=2)
print("✅ Swagger spec saved as single-endpoint-swagger.json")

# Step 6: Generate runnable k6 test script
method = doc["method"].lower()
path = doc["path"]

# Separate query parameters and headers
query_params = []
header_params = []

for param in doc.get("request_parameter", []):
    if param.lower().startswith("x-"):  # heuristic: treat X-* as headers
        header_params.append(param)
    else:
        query_params.append(param)

query_string = ""
if query_params:
    query_string = "?" + "&".join([f"{p}=test" for p in query_params])

headers_block = ""
if header_params:
    headers = ",\n    ".join([f"'{p}': 'test'" for p in header_params])
    headers_block = f"""
    headers: {{
      {headers}
    }}"""

request_options = f"{{{headers_block}\n}}" if headers_block else "{}"

k6_script = f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export let options = {{
  vus: 10,
  duration: '30s',
}};

export default function () {{
  let res = http.{method}('https://localhost:8081{path}{query_string}', {request_options});
  check(res, {{
    'status is 200': (r) => r.status === 200,
  }});
  sleep(1);
}}
"""

# Step 7: Save k6 script
os.makedirs("k6-tests", exist_ok=True)
filename = f"k6-tests/test-{method}-{path.strip('/').replace('/', '_')}.js"
with open(filename, "w") as f:
    f.write(k6_script.strip())

print(f"✅ k6 test script saved as: {filename}")
