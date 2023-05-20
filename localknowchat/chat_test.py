import openai
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

os.environ["OPENAI_API_KEY"] = "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"


def prompt(question, answers):
    demo_q = '成人头疼，流鼻涕是感冒还是过敏？'
    demo_a = '成人出现头痛和流鼻涕的症状，可能是由于普通感冒或常年过敏引起的。如果病人出现咽喉痛和咳嗽，感冒的可能性比较大；而如果出现口、喉咙' \
             '发痒、眼睛肿胀等症状，常年过敏的可能性比较大。'
    system = f'你是一个的中医机器人，你的任务是回答客户的问题，在用户询问你之前，我们会尝试给你一段相关的资料，如果用户提问的信息与我们给你的资' \
             f'料不相关或者没有给你资料，就回答未查到相关信息。示例格式：用户提问：{demo_q}。回复：{demo_a}'

    q = '参考资料：'
    for index, answer in enumerate(answers):
        q += str(index + 1) + '. ' + str(answer['title']) + ': ' + str(answer['text']) + '\n'
    q += "用户提问：" + question + '\n'
    res = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': q},
    ]
    return res


def query(text):
    """
    执行逻辑：
    首先使用openai的Embedding API将输入的文本转换为向量
    然后使用Qdrant的search API进行搜索，搜索结果中包含了向量和payload
    payload中包含了title和text，title是疾病的标题，text是摘要
    最后使用openai的ChatCompletion API进行对话生成
    """
    client = QdrantClient("127.0.0.1", port=6333)
    collection_name = "data_collection"
    load_dotenv()
    openai.api_key = os.getenv("OPENAI_API_KEY")

    sentence_embeddings = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )

    """
    因为提示词的长度有限，所以我只取了搜索结果的前三个，如果想要更多的搜索结果，可以把limit设置为更大的值
    """
    search_result = client.search(
        collection_name=collection_name,
        query_vector=sentence_embeddings["data"][0]["embedding"],
        limit=4,
        search_params={"exact": False, "hnsw_ef": 128}
    )
    answers = []
    tags = []
    """
    因为提示词的长度有限，每个匹配的相关摘要我在这里只取了前300个字符，如果想要更多的相关摘要，可以把这里的300改为更大的值
    """
    for result in search_result:
        if len(result.payload["text"]) > 300:
            summary = result.payload["text"][:300]
        else:
            summary = result.payload["text"]

        answers.append({"title": result.payload["title"], "text": summary})
    promptMessage = prompt(text, answers)
    print(f'promptMessage:{promptMessage}')

    completion = openai.ChatCompletion.create(
        temperature=0.7,
        model="gpt-3.5-turbo",
        messages=promptMessage,
    )

    return {
        "answer": completion.choices[0].message.content,
        "tags": tags,
    }


if __name__ == '__main__':
    openai.proxy = "127.0.0.1:7890"
    question = "如果我的减肥菜单没有油，会不会导致便秘？？"  # 要提问的问题
    result = query(question)  # 调用 query 函数进行提问
    answer = result["answer"]  # 获取回答内容
    print("回答:", answer)
