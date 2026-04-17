from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")

query = {
    "_source": ["title"],
    "query": {
        "bool": {
            "must": [
                {"match": {"title": "Java"}},
                {"match": {"release_date": "2018-11-30"}},
            ]
        }
    },
}

searchResponse = client.search(index="books", body=query)
print("#######")
print(searchResponse["hits"]["hits"])
