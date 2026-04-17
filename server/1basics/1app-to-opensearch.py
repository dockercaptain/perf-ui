from opensearchpy import OpenSearch
import time
import requests
from sentence_transformers import SentenceTransformer
import google.generativeai as genai


# Step 1: Connect to OpenSearch

client = OpenSearch(hosts=[{'host': '192.168.1.150', 'port': 9200}])

index_name = "openapi-spec"
 
# Step 2: Fetch Swagger Spec

swagger_url = "http://localhost:8081/swagger/swagger.json"

response = requests.get(swagger_url)

spec = response.json()
sentensemodel = SentenceTransformer("all-MiniLM-L6-v2")

# Step 3: Delete and recreate index

if client.indices.exists(index=index_name):
    client.indices.delete(index=index_name, ignore_unavailable=True)
    print(f"Deleted existing index: {index_name}")
 
mapping = {
    "settings": {
      "index": {
        "knn": "true"
      }
    },
    "mappings": {
        "properties": {
            "path": {"type": "keyword"},
            "method": {"type": "keyword"},
            "summary": {"type": "text"},
            "description": {"type": "text"},
            "tags": {"type": "keyword"},
            "request_parameter": {"type": "keyword"},
            "responses": {"type": "keyword"},
            "semantic_text": {"type": "text", "analyzer": "standard"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 384,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib"
                    }
            }
        }
    }
}

time.sleep(1)

client.indices.create(index=index_name,body=mapping)
print(f"Created index: {index_name}")

time.sleep(1)
# res = client.search(index="openapi-spec", body={"query": {"match_all": {}}}, size=1)

# Step 4: Configure Gemini


genai.configure(api_key="AIzaSyAjTPS6kxScAPhZB_RphkzHiBeXeFMvKUw")
model = genai.GenerativeModel("gemini-2.0-flash")
 
# Step 5: Process and index each endpoint

for path, methods in spec.get("paths", {}).items():

    for method, details in methods.items():

        # Extract response descriptions

        responses_data = {}
        for status_code, response in details.get("responses", {}).items():
            responses_data[status_code] = {
                "response_description": response.get("description", ""),
                "content": response.get("content", {})

            }
 
        # Build prompt for semantic summary

        prompt = f"""

        You are an API documentation assistant. Given the following Swagger endpoint, generate a clear, human-friendly description that combines all relevant details for semantic search. Respond with one paragraph in natural language.

        Method: {method.upper()}
        Path: {path}
        Summary: {details.get("summary", "")}
        Description: {details.get("description", "")}
        Parameters: {[p['name'] for p in details.get("parameters", [])]}
        Responses: {responses_data}

        """
 
        # print(prompt)
        # Generate semantic summary

        semantic_response = model.generate_content(prompt)
        semantic_text = semantic_response.text.strip()
        embedding = sentensemodel.encode(semantic_text).tolist()
 
        # Build document
        doc = {
            "path": path,
            "method": method.upper(),
            "summary": details.get("summary", ""),
            "description": details.get("description", ""),
            # "tags": details.get("tags", []),
            "tags": [str(tag) for tag in details.get("tags", [])],   # ensure strings
            # "request_parameter": [p['name'] for p in details.get("parameters", [])],
            "request_parameter": [str(p.get("name", "")) for p in details.get("parameters", [])],
            # "responses": list(details.get("responses", {}).keys()),
            "responses": [str(code) for code in details.get("responses", {}).keys()],  # force string
            "semantic_text": semantic_text,
            "embedding": embedding
        }
        # Index into OpenSearch

        client.index(index=index_name, body=doc)
        print(f"Indexed: {method.upper()} {path}")

 