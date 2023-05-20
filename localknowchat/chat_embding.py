from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.http.models import PointStruct
from dotenv import load_dotenv
from common.log import logger
import os
from tqdm import tqdm
import openai

openai.proxy = "127.0.0.1:7890"
os.environ["OPENAI_API_KEY"] = "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"


class QdrantDataUploader:
    def __init__(self, collection_name, recreate_collection=True, check_duplicates=True):
        self.collection_name = collection_name
        self.recreate_collection = recreate_collection
        self.check_duplicates = check_duplicates
        self.client = QdrantClient("127.0.0.1", port=6333)
        load_dotenv()
        openai.api_key = os.getenv("OPENAI_API_KEY")

    def to_embeddings(self, items):
        sentence_embeddings = openai.Embedding.create(
            model="text-embedding-ada-002",
            # items[0]是标题，items[1]是内容
            input=items[0] + items[1]
            # input = items[0]
            # input=items[1]
        )
        print(
            f'[items[0]{items[0]},\n items[1]:{items[1]},\n sentence_embeddings["data"][0]["embedding"]]:{sentence_embeddings["data"][0]["embedding"]}')
        return [items[0], items[1], sentence_embeddings["data"][0]["embedding"]]

    def upload_data(self, data_dir):
        collection_info = self.client.get_collection(self.collection_name)
        logger.info(collection_info)
        if self.recreate_collection:
            self.client.delete_collection(self.collection_name)
            collection_info = None
        if collection_info is None:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
        count = 0
        for root, dirs, files in os.walk(data_dir):
            for file in tqdm(files, desc="Uploading files"):
                # 循环代码
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                    parts = text.split('#####')
                    item = self.to_embeddings(parts)

                    if self.check_duplicates:
                        duplicate_points = self.client.search(
                            collection_name=self.collection_name,
                            query_vector=item[2],
                            top=1
                        )

                        if duplicate_points and duplicate_points[0].payload['text'] == item[1]:
                            logger.info("已存在相同数据")
                            continue

                    self.client.upsert(
                        collection_name=self.collection_name,
                        wait=True,
                        points=[
                            PointStruct(id=count, vector=item[2], payload={"title": item[0], "text": item[1]}),
                        ],
                    )
                    count += 1

    # query_vector = [1.0] * 1536
    def delete_data_by_title(self, title):
        if not title:
            logger.info("标题不能为空")
            return

        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=[1.0] * 1536,  # Placeholder non-zero vector
            query={"title": title},
            limit=39  # 设置为想要的结果数量
        )

        found = False
        for result in search_results:
            print(f"{result} \n")
            if result.payload['title'] == title:
                data_id = result.id
                # 使用 Ids 类型的选择器对象
                points_selector = [data_id]
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=points_selector
                )
                logger.info(f"已删除标题为'{title}'的数据点")
                found = True
                break
        if not found:
            logger.info(f"未找到标题为'{title}'的数据点或数据已删除")


if __name__ == '__main__':
    collection_name = "data_collection"
    data_dir = "./train_data"
    uploader = QdrantDataUploader(collection_name, recreate_collection=True, check_duplicates=True)
    uploader.upload_data(data_dir)
    # 示例：根据标题删除数据
    # title_to_delete = "品牌故事是什么？"
    # uploader.delete_data_by_title(title_to_delete)
