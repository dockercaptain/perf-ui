from sentence_transformers import SentenceTransformer
from opensearchpy import OpenSearch

# Connect to OpenSearch
client = OpenSearch(hosts=[{'host': '192.168.1.150', 'port': 9200}])
index_name = "openapi-spec"

# Load the same embedding model
sentencemodel = SentenceTransformer("all-MiniLM-L6-v2")

# Your semantic query
query_text = "give me  found api"

# Convert to embedding
query_embedding = sentencemodel.encode(query_text).tolist()

# Build k-NN query
knn_query = {
    "size": 1,  # number of results to return
    "query": {
        "knn": {
            "embedding": {
                "vector": query_embedding,
                "k": 384
            }
        }
    },
    "_source": ["path", "method", "summary", "semantic_text"]
}

# Execute search
response = client.search(index=index_name, body=knn_query)

# Display results
print("\n🔍 Top Semantic Matches:")
for hit in response["hits"]["hits"]:
    source = hit["_source"]
    score = hit["_score"]
    print(f"- [{score:.2f}] {source['method']} {source['path']}: {source['semantic_text']}")
