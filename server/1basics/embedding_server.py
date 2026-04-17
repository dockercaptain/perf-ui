import json
import aiohttp
import asyncio
import chromadb
from sentence_transformers import SentenceTransformer

# 1. Initialize embedding model + Chroma client
embedder = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path="./swagger_chroma")
collection = chroma_client.get_or_create_collection("swagger_endpoints")


# 2. Fetch Swagger JSON
async def fetch_swagger(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()


# 3. Flatten Swagger into documents
def swagger_to_docs(swagger: dict) -> list[dict]:
    docs = []
    for path, methods in swagger.get("paths", {}).items():
        for method, details in methods.items():
            text_parts = [
                f"{method.upper()} {path}",
                details.get("summary", ""),
                details.get("description", "")
            ]

            # parameters
            params = details.get("parameters", [])
            for p in params:
                text_parts.append(
                    f"Param {p['name']} ({p['in']}): {p.get('description','')}"
                )

            # request body
            if "requestBody" in details:
                text_parts.append(f"RequestBody: {json.dumps(details['requestBody'])}")

            docs.append({
                "id": f"{method.upper()}_{path}",
                "text": "\n".join(text_parts),
                "path": path,
                "method": method.upper(),
                "summary": details.get("summary", ""),
                "parameters": params,
                "requestBody": details.get("requestBody", {})
            })
    return docs


# 4. Safe metadata conversion for Chroma
def safe_metadata(d: dict) -> dict:
    meta = {}
    for k, v in d.items():
        if k == "text":
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            meta[k] = v
        else:
            meta[k] = json.dumps(v)  # stringify lists/dicts
    return meta


# 5. Store in ChromaDB
def store_docs(docs: list[dict]):
    embeddings = embedder.encode([d["text"] for d in docs]).tolist()
    collection.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        metadatas=[safe_metadata(d) for d in docs],
        embeddings=embeddings
    )


# 6. Query ChromaDB
def query_swagger(question: str, top_k: int = 1):
    q_emb = embedder.encode([question]).tolist()
    results = collection.query(query_embeddings=q_emb, n_results=top_k)
    return results


# 7. Format answer
def format_answer(result: dict) -> str:
    if not result["documents"]:
        return "No relevant Swagger endpoint found."
    doc = result["documents"][0][0]
    meta = result["metadatas"][0][0]

    return f"""
✅ Matched Endpoint
- Path: {meta['path']}
- Method: {meta['method']}
- Summary: {meta.get('summary', '')}

Swagger Info:
{doc}
"""


# ------------------ MAIN FLOW ------------------

async def main():
    swagger_url = "http://localhost:8081/swagger/download"
    print(f"Fetching Swagger from {swagger_url} ...")
    swagger = await fetch_swagger(swagger_url)

    # Convert + store
    docs = swagger_to_docs(swagger)
    store_docs(docs)
    print(f"Stored {len(docs)} endpoints in ChromaDB ✅")

    # Interactive Q&A
    while True:
        q = input("\nAsk a Swagger question (or 'exit'): ")
        if q.lower() == "exit":
            break
        result = query_swagger(q)
        print(format_answer(result))


if __name__ == "__main__":
    asyncio.run(main())
