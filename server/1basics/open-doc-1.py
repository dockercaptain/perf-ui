from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")
# print(type(client.info()))
# print(client.info()["version"]["number"])

index_name="books"
index_settings={}
if client.indices.exists(index=index_name):
    print("")
    # print("index exists--\n", client.indices.get(index=index_name))
else:
    response=client.indices.create(index=index_name,body=index_settings)
    if response["acknowledged"==True]:
        print("successfully created index")

#### 

doc1={
  "title":"Effective Java",
  "author":"Joshua Bloch",
  "release_date":"2001-06-01",
  "amazon_rating":4.7,
  "best_seller":True,
  "prices": {
    "usd":9.95,
    "gbp":7.95,
    "eur":8.95
  }
}
doc_id=1
updated_doc1={
    "doc": doc1
}


docResponse=client.update(index=index_name, body=updated_doc1, id=doc_id)
print(docResponse)