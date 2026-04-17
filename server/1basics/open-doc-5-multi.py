from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")

query = {
    "query": {
        "match": {
            "get.summary": {
                "query": "bad"
            }
        }
    }
}

# searchResponse=client.search(index="books",body=query)
#match all vs just index name both are the same
searchResponse=client.search(index="apipaths", body=query)
print("#######")
print(searchResponse)
# for res in searchResponse["hits"]["hits"]:
#     print(res["_source"])
