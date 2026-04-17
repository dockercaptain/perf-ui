from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")

query = {
        "_source": ["title"],
    "query": {
        "fuzzy": {
            "title": {
                "value":  "kkva",
                "fuzziness": 4
             }
        }
    }
}

searchResponse=client.search(index="books", body=query)
print("#######")
print(searchResponse["hits"]["hits"])
