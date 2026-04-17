from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opensearchpy import OpenSearch
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn

# --- Configuration ---
OPENSEARCH_HOST = "192.168.1.150"
OPENSEARCH_PORT = 9200
OPENSEARCH_INDEX = "openapi-spec"
# ---------------------

# Initialize the FastAPI application
app = FastAPI(
    title="OpenSearch OpenAPI Spec API",
    description="An API to retrieve 'method', 'path', and 'id' from OpenSearch's 'openapi-spec' index.",
    version="1.0.0"
)

# ⭐️ CORSMiddleware Configuration ⭐️
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. CORRECTED: Define a Pydantic Model for the single item in the response list.
class SwaggerSpec(BaseModel):
    # These fields match the expected output structure
    id: str
    method: str
    path: str


@app.get(
    "/getswagger",
    # 2. Use List[SwaggerSpec] as the response model
    response_model=List[SwaggerSpec],
    summary="Retrieve OpenAPI ID, method, and path information"
)
async def get_openapi_specs():
    """
    Connects to OpenSearch, queries the 'openapi-spec' index for
    'method' and 'path' fields, and returns the results including the document '_id'.
    """
    try:
        # 1. Initialize the OpenSearch client
        client = OpenSearch(
            hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
            use_ssl=False,
            verify_certs=False,
        )
        
        # 2. Define the search query
        query = {
            "_source": ["method", "path"],
            "query": {
                "match_all": {}
            }
        }
       
        # 3. Execute the search query
        searchResponse = client.search(index=OPENSEARCH_INDEX, body=query)
        
        # 4. FIX: Process the response to extract _id and _source fields 
        # and return as a list of dictionaries/Pydantic models.
        results = []
        for res in searchResponse["hits"]["hits"]:
            
            # The FastAPI framework handles the final conversion to the SwaggerSpec model
            # as long as the dictionary keys match the model field names.
            results.append({
                "id": res["_id"],
                "path": res["_source"]["path"],
                "method": res["_source"]["method"],
            })
            
        print("#####")
        # print(results) # Print the dictionary list, not the attempted SwaggerSpec objects
        return results
        
    except Exception as e:
        # 5. Handle potential errors
        print(f"Error connecting to OpenSearch or executing query: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve data from OpenSearch. Error: {str(e)}"
        )
 
if __name__ == "__main__":
    uvicorn.run("2list-method-path:app", host="127.0.0.1", port=8000, reload=True)