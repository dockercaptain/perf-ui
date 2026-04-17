


from opensearchpy import OpenSearch
import requests
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import time

# ===== Connect to OpenSearch =====
client = OpenSearch(hosts=[{"host": "192.168.1.150", "port": 9200}])
index_name = "openapi-spec"

# ===== Fetch Swagger Spec =====
swagger_url = "http://localhost:8081/swagger/swagger.json"
spec = requests.get(swagger_url).json()

# ===== Delete & recreate index =====
if client.indices.exists(index=index_name):
    client.indices.delete(index=index_name, ignore_unavailable=True)

mapping = {
    "settings": {"index": {"knn": True}},  # boolean is correct
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
            "embedding": {"type": "knn_vector", "dimension": 384}
        }
    }
}

time.sleep(1)
client.indices.create(index=index_name, body=mapping)
time.sleep(1)

# ===== Configure Gemini =====
genai.configure(api_key="AIzaSyAjTPS6kxScAPhZB_RphkzHiBeXeFMvKUw")
model = genai.GenerativeModel("gemini-2.0-flash")

# ===== Init SentenceTransformer =====
s_model = SentenceTransformer("all-MiniLM-L6-v2")

# ===== Index Swagger endpoints =====
for path, methods in spec.get("paths", {}).items():
    for method, details in methods.items():
        responses_data = {str(k): v.get("description", "") for k, v in details.get("responses", {}).items()}
        prompt = f"""
        You are an API documentation assistant. Generate a clear human-friendly description
        for semantic search.

        Method: {method.upper()}
        Path: {path}
        Summary: {details.get("summary", "")}
        Description: {details.get("description", "")}
        Parameters: {[p.get('name', '') for p in details.get("parameters", [])]}
        Responses: {responses_data}
        """
        semantic_text = model.generate_content(prompt).text.strip()
        embedding = [float(x) for x in s_model.encode(semantic_text).tolist()]

        doc = {
            "path": str(path),
            "method": str(method.upper()),
            "summary": str(details.get("summary", "")),
            "description": str(details.get("description", "")),
            "tags": [str(tag) for tag in details.get("tags", [])],
            "request_parameter": [str(p.get("name", "")) for p in details.get("parameters", [])],
            "responses": [str(k) for k in details.get("responses", {}).keys()],
            "semantic_text": semantic_text,
            "embedding": embedding
        }
        client.index(index=index_name, body=doc)
        print(f"Indexed {method.upper()} {path}")

# ===== Semantic Search Example =====
user_query = "/bad"
query_vector = [float(x) for x in s_model.encode(user_query).tolist()]
query = {
    "size": 5,
    "query": {
        "knn": {
            "embedding": {
                "vector": query_vector,
                "k": 5,
                "num_candidates": 100
            }
        }
    }
}

res = client.search(index=index_name, body=query)
for hit in res["hits"]["hits"]:
    print(hit["_source"]["method"], hit["_source"]["path"], "=>", hit["_score"])
