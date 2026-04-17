from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")
# print(type(client.info()))
# print(client.info()["version"]["number"])

# query = {
#     "query": {
#         "match": {
#             "author": "jo"
#         }
#     }
# }


# query = {
#     "query": {
#         "prefix": {
#             "author": "jo"
#         }
#     }
# }

query = {
    "query": {
        "match": {
            "author": {
                "query": "Herbert Schildt",
                "operator": "AND"
            }

        }
    }
}

# searchResponse=client.search(index="books",body=query)
#match all vs just index name both are the same
searchResponse=client.search(index="books", body=query)

print("#######")
print(searchResponse)
# for res in searchResponse["hits"]["hits"]:
#     print(res["_source"])
