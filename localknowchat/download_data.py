# -*- coding: utf-8 -*-
import os
from qdrant_client import QdrantClient
import json

if __name__ == '__main__':
    client = QdrantClient("127.0.0.1", port=6333)
    collection_name = "data_collection"
    savepath = "download_data"
    filename = "collection_data.json"

    # 构建一个空的查询向量
    query_vector = [0.0] * 1536

    # 查询集合中的所有数据
    response = client.search(collection_name=collection_name, query={"match_all": {}}, query_vector=query_vector)
    print(response)
    data = [item.payload for item in response]  # 提取每个元素的 payload 属性

    # 保存数据到本地文件
    with open(os.path.join(savepath, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

