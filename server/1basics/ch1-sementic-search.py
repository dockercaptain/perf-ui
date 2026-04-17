from opensearchpy import OpenSearch

import requests
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
# Step 1: Connect to OpenSearch
client = OpenSearch(hosts=[{'host': '192.168.1.150', 'port': 9200}])
# print(client.info())
index_name = "openapi-spec"


user_query = "/bad"
 
 
sentensemodel = SentenceTransformer("all-MiniLM-L6-v2")
query_vector  = sentensemodel.encode(user_query).tolist()

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

print(client.indices.get_mapping(index="openapi-spec"))
print("################")
response = client.search(index="openapi-spec", body=query)
print(response)
