import requests
import json
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


# -------------------------------------------------------------------
# 1. Load Swagger JSON
# -------------------------------------------------------------------
url = "http://localhost:8081/swagger/swagger.json"
swagger = requests.get(url).json()

documents = []

# -------------------------------------------------------------------
# 2. Convert Swagger into smaller documents
# -------------------------------------------------------------------
for path, methods in swagger.get("paths", {}).items():
    for method, details in methods.items():
        summary = details.get("summary", "")
        description = details.get("description", "")
        tags = details.get("tags", [])
        parameters = details.get("parameters", [])
        request_body = details.get("requestBody", {})
        responses = details.get("responses", {})

        metadata_base = {
            "type": "api_endpoint",
            "path": path,
            "method": method.upper(),
            "tags": ", ".join(tags),
            "summary": summary,
        }

        # ---- Summary & Description ----
        if summary or description:
            documents.append(Document(
                page_content=f"Endpoint: {method.upper()} {path}\nSummary: {summary}\nDescription: {description}",
                metadata={**metadata_base, "section": "summary"}
            ))

        # ---- Parameters (headers, query params etc.) ----
        if parameters:
            documents.append(Document(
                page_content=f"Parameters:\n{json.dumps(parameters, indent=2)}",
                metadata={**metadata_base, "section": "parameters"}
            ))

        # ---- Request Body ----
        if request_body:
            documents.append(Document(
                page_content=f"Request Body:\n{json.dumps(request_body, indent=2)}",
                metadata={**metadata_base, "section": "request_body"}
            ))

        # ---- Responses ----
        if responses:
            for status, response in responses.items():
                documents.append(Document(
                    page_content=f"Response {status}:\n{json.dumps(response, indent=2)}",
                    metadata={**metadata_base, "section": "response", "status": status}
                ))

# -------------------------------------------------------------------
# 3. Embeddings + Vector Store
# -------------------------------------------------------------------
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Create DB fresh (persist to disk)
db = Chroma.from_documents(
    documents,
    embedding_model,
    persist_directory="./swagger_index"
)

# -------------------------------------------------------------------
# 4. Semantic Search Function
# -------------------------------------------------------------------
def search_swagger(query: str, k: int = 5):
    """Search Swagger docs using embeddings."""
    results = db.similarity_search(query, k=k)
    for doc in results:
        print("Match:", doc.metadata["method"], doc.metadata["path"], "-", doc.metadata.get("section"))
        if "status" in doc.metadata:
            print("Status:", doc.metadata["status"])
        print(doc.page_content[:400])
        print("-" * 80)

# -------------------------------------------------------------------
# 5. Example Queries
# -------------------------------------------------------------------
print("\n--- Example 1: give me authorize request ---")
search_swagger("give me authoriz?",k=2)

# print("\n--- Example 2: Unauthorized error ---")
# search_swagger("What does 401 unauthorized mean?")
