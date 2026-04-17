from opensearchpy import OpenSearch
import json
import os
import requests

# # Step 1: Connect to OpenSearch
# client = OpenSearch(hosts=[{'host': '192.168.1.150', 'port': 9200}])
# index_name = "openapi-spec"

url="http://localhost:8081/swagger/download"
resp=requests.get(url=url)
data=resp.json()

# Step 2: Define the endpoint to extract
target_path = "/ok"         # Change as needed
target_method = "get"       # Change as needed

okApi = dict()
okApi["paths"]={}
okApi["paths"][target_path]=data["paths"][target_path]
okApi["swagger"]=data["swagger"]
okApi["info"]=data["info"]
data["host"]="localhost:8081"
okApi["host"]=data["host"]
okApi["basePath"]=data["basePath"]
okApi["schemes"]=data["schemes"]
# okApi["method"]=data["paths"]["method"]
# print(okApi)


# Step 5: Save Swagger spec (optional)
with open("single-endpoint-swagger.json", "w") as f:
    json.dump(okApi, f, indent=2)
print("✅ Swagger spec saved as single-endpoint-swagger.json")


# # Separate query parameters and headers
query_params = []
header_params = []
parameters = okApi["paths"][target_path][target_method]["parameters"][0]
for param in parameters:
    parameter=str(parameters[param])
    if parameter.lower().startswith("x-"):  # heuristic: treat X-* as headers
        header_params.append(parameter)
    else:
        query_params.append(parameter)
# query_string = ""
# if query_params:
#     query_string = "?" + "&".join([f"{p}=test" for p in query_params])

headers_block = ""
if header_params:
    headers = ",\n    ".join([f"'{p}': 'test'" for p in header_params])
    headers_block = f"""
    headers: {{
      {headers}
    }}"""


request_options = f"{{{headers_block}\n}}" if headers_block else "{}"