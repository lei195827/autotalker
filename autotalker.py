# encoding:utf-8

import plugins
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.expired_dict import ExpiredDict
from common.log import logger
from config import conf
from plugins import *
from lib import itchat
from lib.itchat.content import *
from channel.chat_message import ChatMessage


# https://github.com/bupticybee/ChineseAiDungeonChatGPT
@plugins.register(
    name="autotalker",
    desire_priority=0,
    namecn="回复脚本",
    desc="A plugin for regular replies and mass messaging",
    version="1.0",
    author="lei",
)
class AutoReply(Plugin):
    def __init__(self):
        super().__init__()
        self.nickname_user_dict = {}
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        logger.info("[AutoReply] inited")
        # 目前没有设计session过期事件，这里先暂时使用过期字典
        # , "Y.J.Cai"
        self.user_list = ['墨染倾城']

    def get_receiverif_dict(self):
        # 获取微信好友的信息,返回的是字典
        friends = itchat.get_friends(update=True)[0:]
        logger.info(friends)
        for friend in friends:
            # 获取好友的昵称和receiver id
            nickname = friend['NickName']
            user_id = friend['UserName']
            # 去掉昵称两边的空格
            nickname = nickname.strip()
            # 替换掉昵称中的特殊字符，比如单引号、双引号、冒号等
            nickname = nickname.replace("'", "").replace('"', "").replace(":", "")
            # 把昵称和receiver id作为键值对存入新字典中
            self.nickname_user_dict[nickname] = user_id
            # 把昵称和receiver id作为键值对存入新字典中
            self.nickname_user_dict[nickname] = user_id
        logger.info(self.nickname_user_dict)

    def confirm_ichat(self):
        if itchat.instance is None:
            logger.info("Wechat instance has not been created yet.")
            return False
        else:
            logger.info("Wechat instance is already created.")
            return True

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        if self.nickname_user_dict == {}:
            self.get_receiverif_dict()
        bottype = Bridge().get_bot_type("chat")
        if bottype not in [const.OPEN_AI, const.CHATGPT, const.CHATGPTONAZURE]:
            return
        ichat_is_load = self.confirm_ichat()
        content = e_context["context"].content[:]
        msgs = e_context["context"]["msg"]
        clist = e_context["context"].content.split(maxsplit=1)
        # sessionid = e_context["context"]["session_id"]
        receive_id = self.nickname_user_dict["墨染倾城"]
        # receive_id = msgs.from_user_id
        logger.debug("[AutoReply] on_handle_context. content: %s" % clist)
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        if clist[0] == f"{trigger_prefix}群发消息":
            if ichat_is_load:
                for user_nickname in self.user_list:
                    receive_id = self.nickname_user_dict[str(user_nickname)]
                    if len(clist) > 1:
                        itchat.send(f"群发:{str(clist[1:])[2:-2]}", toUserName=receive_id)
                        logger.info(f"receive_id:{receive_id}")
                    else:
                        itchat.send("群发测试", toUserName=receive_id)
                        logger.info(f"receive_id:{receive_id}")
            e_context.action = EventAction.BREAK_PASS
        elif clist[0] == f"{trigger_prefix}获取好友字典":
            self.get_receiverif_dict()
            if ichat_is_load:
                itchat.send("刷新好友列表", toUserName=receive_id)
                logger.info(f"receive_id:{receive_id}")
            e_context.action = EventAction.BREAK_PASS

    def get_help_text(self, **kwargs):
        help_text = "可以定时发送消息或者群发消息。\n"
        if kwargs.get("verbose") != True:
            return help_text
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        help_text = f"{trigger_prefix}群发消息 <消息内容> - 将<消息内容>群发给指定的用户。\n"
        if kwargs.get("verbose") == True:
            help_text += f"\n{trigger_prefix}定时发送 - 当用户5分钟没再发送消息，发送一次聊天信息。"
        return help_text
