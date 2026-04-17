from fastapi import FastAPI
from opensearchpy import OpenSearch
from typing import List
import uvicorn

app = FastAPI()

# Initialize OpenSearch client
client = OpenSearch(hosts=[{"host": "192.168.1.150", "port": 9200}])

@app.get("/search", response_model=List[dict])
def search_openapi_spec():
    query = {
        "_source": ["method", "path"],
        "query": {
            "match_all": {}
        }
    }

    search_response = client.search(index="openapi-spec", body=query)
    results = [res["_source"] for res in search_response["hits"]["hits"]]
    return results

# Run the app on port 8888
if __name__ == "__main__":
    uvicorn.run("2list-method-path.py:app", host="0.0.0.0", port=8888, reload=True)
