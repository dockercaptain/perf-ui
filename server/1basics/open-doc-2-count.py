from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")
# print(type(client.info()))
# print(client.info()["version"]["number"])

index_name="books"

docResponse=client.count(index=index_name)
print(docResponse)

searchResponse=client.search(index=index_name)
print("#######")
# for res in searchResponse["hits"]["hits"]:
#     print(res["_source"])

print([ res["_source"]['title'] for res in searchResponse["hits"]["hits"]])

#search specific document by id
print(client.get(index=index_name, id=1))