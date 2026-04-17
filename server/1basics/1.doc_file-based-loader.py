from langchain.document_loaders import TextLoader

loader1 = TextLoader("file1.txt")
loader2 = TextLoader("file2.txt")
document=loader1.load()
another_document=loader2.load()
document.extend(another_document)

print(type(document))

print(len(document))
print("@@@@@@")
# for doc in document:
#     doc.metadata["category"]="biodata"
#     doc.metadata["region"]="india"
#     doc.metadata["timestamp"]="2025-09-20"
# document=loader2.load()

document[0].metadata["author"] = "LangChain User"
for doc in document:
    doc.metadata["category"]="otherdata"
    doc.metadata["region"]="pakistan"

# for doc in document:
#     print(doc.metadata)

print("#########################")
print(type(document))
