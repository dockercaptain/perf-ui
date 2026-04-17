from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")

query = {
    "_source": ["title"],
    "query": {
        "match_phrase_prefix": {
            "title": "java",
             }
        },
        "highlight": {
            "fields": {
            "title": {} # make sure field name is same 
            }
        }
    }

searchResponse=client.search(index="books", body=query)
print("#######")
print(searchResponse["hits"]["hits"])
