from opensearchpy import OpenSearch
import time


client = OpenSearch(host="192.168.1.150", port="9200")

# Define source and destination indices
source_index = 'books' #'logs-old'
destination_index = 'new-books'#'logs-new'

# Step 1: Create the destination index with new mapping
client.indices.create(
    index=destination_index,
    body={
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "message": {"type": "text", "analyzer": "english"},
                "level": {"type": "keyword"},
                "host": {"type": "keyword"}
                # Add other fields as needed
            }
        }
    }
)

# Step 2: Reindex from source to destination
reindex_response = client.reindex(
    body={
        "source": {"index": source_index},
        "dest": {"index": destination_index}
    },
    wait_for_completion=True,
    request_timeout=300
)

print("Reindexing complete:", reindex_response)

# Optional: Delete old index if needed
# client.indices.delete(index=source_index)
