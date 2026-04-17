from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")

query = {
    "_source": ["operating_system", "price_usd"],
    "query": {
        "bool": {
            "must": [
                {"match": {"bluetooth": "true"}},
                {
                    "match_phrase": {
                        "name": {"query": "LG"},
                    }
                },
            ],
            "must_not":[
                {
                    "range": {"price_usd": {"gt": 50}}
                }
            ]
            # "should": [
            #     {
            #         "match": {"operating_system": "Android"} # "change to ABC"
            #     }
            # ]
        }
    },
}

searchResponse = client.search(index="mobile_phones", body=query)
print("#######")
print(searchResponse["hits"]["hits"])
