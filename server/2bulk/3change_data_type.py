from opensearchpy import OpenSearch

client = OpenSearch(host="192.168.1.150", port="9200")
# print(type(client.info()))
# print(client.info()["version"]["number"])

index_name="bulklogs"

#type coehercion works means if can be converted easily then fine
#otherwise won't be able to create the docuemnt it data type changes later
doc={"timestamp": "2025-09-26T10:00:00Z", "host": "api-01", "level": "WARN", "message": "Access denied for user 'devops' on /secure/data", "status_code": 200, "user": "devops", "path": "/secure/data", "ip": "132.94.240.233", "user_agent": "Python-urllib/3.9", "method": "POST", "geo": {"country": "RU", "city": "Moscow", "asn": 12389}, "response_time_ms": "4iiiiiii89", "referrer": "https://example.com/secure/data", "session_id": "sess-000000", "key_values": {"ip": "132.94.240.233", "status_code": 200, "user": "devops", "path": "/secure/data", "geo_country": "RU", "geo_city": "Moscow", "asn": 12389}}

resp=client.create(index=index_name,body=doc, id=10000000)
print(resp)

#search specific document by id
