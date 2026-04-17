from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")

query = {
    "query": {
        "multi_match": {
            "query": "404",
            "fields": ["get.responses.404.description^3","get.description"], 
            "operator": "AND"

             }
        }
    }


searchResponse=client.search(index="apipaths", body=query)
print("#######")
print(searchResponse)
