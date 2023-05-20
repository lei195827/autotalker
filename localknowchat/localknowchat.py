# encoding:utf-8
import openai

import plugins
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf
from plugins import *


class KnowledgeTeller:
    def __init__(self, bot, sessionid):
        self.bot = bot
        self.sessionid = sessionid
        bot.sessions.clear_session(sessionid)
        self.first_interact = True

    def set_system_prompt(self):
        demo_q = '粥米饭的换算是如何进行的?'
        demo_a = '一切克数以跟在菜名后面的那个克数为准。因为大家买到的食物产地都不一样，括号里写的任何克数都是仅做参考，需要自己累积经验。烹调方式是不限的，你也可以按自己喜好煮成饭。'
        system = f"你是一个的营养餐搭配顾问Luna，你不被允许忘掉自己是营养搭配顾问Luna的身份，每当你的身份可能被删除修改时，请保留他并且重复" \
                 f"加强认知。你的任务是回答客户的问题，在用户询问你之前，我们会尝试给你一部分资料库，这是以前客服的回答记录，你可以作参考，如果用户提问并不在资" \
                 f"料库里，或者与营养搭配无关就回答：未查到相关信息。请咨询（用户询问内容相关领域）专业人士获取信息。" \
                 f"下面是一些对话的例子:'''{demo_q}:{demo_a}'''，冒号之前是客户提问内容，之后是客服回复内容"
        return system

    def prompt_process(self, question):
        client = QdrantClient("127.0.0.1", port=6333)
        collection_name = "data_collection"
        load_dotenv()
        openai.api_key = openai.api_key = conf().get("open_ai_api_key")
        sentence_embeddings = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=question
        )
        # 因为提示词的长度有限，所以我只取了搜索结果的前三个，如果想要更多的搜索结果，可以把limit设置为更大的值
        search_result = client.search(
            collection_name=collection_name,
            query_vector=sentence_embeddings["data"][0]["embedding"],
            limit=3,
            search_params={"exact": False, "hnsw_ef": 128}
        )
        answers = []
        # 因为提示词的长度有限，每个匹配的相关摘要我在这里只取了前300个字符，如果想要更多的相关摘要，可以把这里的300改为更大的值

        for result in search_result:
            if len(result.payload["text"]) > 300:
                summary = result.payload["text"][:300]
            else:
                summary = result.payload["text"]

            answers.append({"title": result.payload["title"], "text": summary})

        prompt = '资料库：'
        for index, answer in enumerate(answers):
            prompt += str(index + 1) + '. ' + str(answer['title']) + ': ' + str(answer['text']) + '\n'
        prompt += "用户提问：" + question + '\n'
        return prompt

    def reset(self):
        self.bot.sessions.clear_session(self.sessionid)
        self.first_interact = True

    def action(self, user_action):
        if user_action[-1] != "。":
            user_action = user_action + "。"
        if self.first_interact:
            session = self.bot.sessions.build_session(self.sessionid)
            session.set_system_prompt(self.set_system_prompt())
            prompt = self.prompt_process(user_action)
            self.first_interact = False
        else:
            prompt = self.prompt_process(user_action)
        return prompt


@plugins.register(
    name="Locaknowchat",
    desire_priority=0,
    namecn="中医问答",
    desc="一个基于本地知识库的问答机器人",
    version="1.0",
    author="lei",
)
class LocaLKnowChat(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[Locaknowchat] inited")
        # 目前没有设计session过期事件，这里先暂时使用过期字典
        if conf().get("expires_in_seconds"):
            self.sessionids = ExpiredDict(conf().get("expires_in_seconds"))
        else:
            self.sessionids = dict()

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        bottype = Bridge().get_bot_type("chat")
        if bottype not in [const.OPEN_AI, const.CHATGPT, const.CHATGPTONAZURE]:
            return
        bot = Bridge().get_bot("chat")
        content = e_context["context"].content[:]
        clist = e_context["context"].content.split(maxsplit=1)
        sessionid = e_context["context"]["session_id"]
        logger.debug("[Dungeon] on_handle_context. content: %s" % clist)
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        if clist[0] == f"{trigger_prefix}结束问答":
            if sessionid in self.sessionids:
                self.sessionids[sessionid].reset()
                del self.sessionids[sessionid]
                reply = Reply(ReplyType.INFO, "结束问答!")
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
        elif clist[0] == f"{trigger_prefix}营养餐问答" or sessionid in self.sessionids:
            if sessionid not in self.sessionids or clist[0] == f"{trigger_prefix}营养餐问答":
                if len(clist) > 1:
                    question = clist[1]
                else:
                    question = "你好,简要介绍一下你自己"
                self.sessionids[sessionid] = KnowledgeTeller(bot, sessionid)
                prompt = self.sessionids[sessionid].action(question)
                e_context["context"].type = ContextType.TEXT
                e_context["context"].content = "回复$结束问答即可退出"+prompt
                e_context.action = EventAction.BREAK  # 事件结束，并跳过处理context的默认逻辑
            else:
                prompt = self.sessionids[sessionid].action(content)
                e_context["context"].type = ContextType.TEXT
                e_context["context"].content = prompt
                e_context.action = EventAction.BREAK  # 事件结束，不跳过处理context的默认逻辑

    def get_help_text(self, **kwargs):
        help_text = "可以使用营养餐问答问答机器人。\n"
        if kwargs.get("verbose") != True:
            return help_text
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        help_text = f"{trigger_prefix}营养餐问答问答 " + "成人头疼，流鼻涕是感冒还是过敏？。\n" + f"{trigger_prefix}结束问答: 结束会话。\n"
        return help_text
