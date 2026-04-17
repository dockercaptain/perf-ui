from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")
# print(type(client.info()))
# print(client.info()["version"]["number"])


index_name="myinex"
index_body={ 
}

# help(client.indices.create)
if client.indices.exists(index=index_name)==False:
    indexResponse=client.indices.create(index=index_name, body=index_body)
    print(indexResponse)
else:
    indexSettings=client.indices.get_settings(index=index_name)
    print("####")
    print(indexSettings)

# delete the index:-
print("####")
IsIndexDeleted=client.indices.delete(index=index_name)
print(IsIndexDeleted)
