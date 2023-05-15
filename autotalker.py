# encoding:utf-8

import plugins
import time
import threading
from bridge.bridge import Bridge
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.expired_dict import ExpiredDict
from common.log import logger
from common.singleton import singleton
from config import conf
from plugins import *
from lib import itchat
from lib.itchat.content import *
from channel.chat_message import ChatMessage


@singleton
class MessageManager:
    def __init__(self, remark_name2user_id_dict, single_blacklist, group_blacklist):
        self.remark_name2user_id_dict = remark_name2user_id_dict
        self.single_blacklist = []
        self.group_blacklist = []
        self.build_blacklist(single_blacklist, group_blacklist)

    def build_blacklist(self, single_blacklist, group_blacklist):
        for single_user in single_blacklist:
            if single_user in self.remark_name2user_id_dict:
                single_id = self.remark_name2user_id_dict[single_user]
                self.single_blacklist.append(single_id)
        for group_user in group_blacklist:
            if group_user in self.remark_name2user_id_dict:
                group_user_id = self.remark_name2user_id_dict[group_user]
                self.group_blacklist.append(group_user_id)
        logger.info(f'group_blacklist:{self.group_blacklist}')
        logger.info(f'single_blacklist:{self.single_blacklist}')

    def check_blacklist(self, cmsg: ChatMessage, e_context: EventContext):
        actual_user_id = cmsg.actual_user_id
        if cmsg.is_group:
            if actual_user_id in self.group_blacklist:
                logger.info("人物处于群回复黑名单中.")
                e_context.action = EventAction.BREAK_PASS
                return True
            else:
                logger.info(f'群组白名单用户')
        else:
            if actual_user_id in self.single_blacklist:
                logger.info("人物处于单人回复黑名单中.")
                e_context.action = EventAction.BREAK_PASS
                return True
            else:
                logger.info(f'单人白名单用户')


# 检查itchat类是否创建的，但感觉好像没啥用
def confirm_ichat():
    if itchat.instance is None:
        logger.info("Wechat instance has not been created yet.")
        return False
    else:
        logger.info("Wechat instance is already created.")
        return True


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
        self.RemarkName2UserName_Dict = {}
        self.UserName2RemarkName_Dict = {}
        self.timers = {}
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.message_manager = None
        logger.info("[AutoReply] inited")
        # 目前没有设计session过期事件，这里先暂时使用过期字典
        # , "Y.J.Cai"
        self.single_blacklist = ['']
        self.group_blacklist = ['程保镭']

    # 定时器回复回调函数
    def timer_reply(self, cmsg: ChatMessage, wait_time):

        itchat.send(f"你好,您还需要帮助吗？（{wait_time}秒自动回复）", toUserName=cmsg.from_user_id)
        logger.info(f"receive_id:{cmsg.from_user_id}")

    def regular_reply(self, cmsg: ChatMessage):
        wait_time = 300.0
        # 获取session的唯一标识符,暂且只处理单人回复
        session_id = cmsg.from_user_id
        # 检查是否存在对应session的定时器
        if session_id in self.timers:
            # 如果存在定时器，重置计时器
            self.timers[session_id].cancel()
            self.timers[session_id] = threading.Timer(wait_time, self.timer_reply, args=[cmsg, 300.0])
        else:
            # 如果不存在定时器，创建一个新的定时器
            self.timers[session_id] = threading.Timer(wait_time, self.timer_reply, args=[cmsg, 300.0])
        # 启动定时器
        self.timers[session_id].start()

    def get_receiver_dict(self):
        # 获取微信好友的信息,返回的是字典
        friends = itchat.get_friends(update=True)[0:]
        logger.info(friends)
        for friend in friends:
            # 获取好友的备注和receiver id
            RemarkName = friend['RemarkName']
            user_id = friend['UserName']
            # 去掉昵称两边的空格
            RemarkName = RemarkName.strip()
            # 替换掉昵称中的特殊字符，比如单引号、双引号、冒号等
            RemarkName = RemarkName.replace("'", "").replace('"', "").replace(":", "")
            # 把昵称和receiver id作为键值对存入新字典中
            self.RemarkName2UserName_Dict[RemarkName] = user_id
            # 把昵称和receiver id作为键值对存入新字典中
            self.RemarkName2UserName_Dict[RemarkName] = user_id
        self.UserName2RemarkName_Dict = {value: key for key, value in self.RemarkName2UserName_Dict.items()}
        logger.info(self.RemarkName2UserName_Dict)

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        if self.RemarkName2UserName_Dict == {}:
            self.get_receiver_dict()
            # 创建黑名单管理器
            self.message_manager = MessageManager(remark_name2user_id_dict=self.RemarkName2UserName_Dict,
                                                  single_blacklist=self.single_blacklist,
                                                  group_blacklist=self.group_blacklist)
        bottype = Bridge().get_bot_type("chat")
        if bottype not in [const.OPEN_AI, const.CHATGPT, const.CHATGPTONAZURE]:
            return

        content = e_context["context"].content[:]
        # 更新定时器
        cmsg = e_context["context"]["msg"]
        self.message_manager.check_blacklist(cmsg, e_context)
        self.regular_reply(cmsg)

        clist = e_context["context"].content.split(maxsplit=1)
        # sessionid = e_context["context"]["session_id"]
        receive_id = self.RemarkName2UserName_Dict["程保镭"]
        # receive_id = msgs.from_user_id
        logger.info(f"{cmsg}")
        logger.debug("[AutoReply] on_handle_context. content: %s" % clist)
        trigger_prefix = conf().get("plugin_trigger_prefix", "$")
        itchat_is_load = confirm_ichat()
        if clist[0] == f"{trigger_prefix}群发消息":
            if itchat_is_load:
                for user_nickname in self.user_list:
                    receive_id = self.RemarkName2UserName_Dict[str(user_nickname)]
                    if len(clist) > 1:
                        itchat.send(f"群发:{str(clist[1:])[2:-2]}", toUserName=receive_id)
                        logger.info(f"receive_id:{receive_id}")
                    else:
                        itchat.send("群发测试", toUserName=receive_id)
                        logger.info(f"receive_id:{receive_id}")
            e_context.action = EventAction.BREAK_PASS
        elif clist[0] == f"{trigger_prefix}获取好友字典":
            self.get_receiver_dict()
            if itchat_is_load:
                itchat.send("刷新好友备注列表", toUserName=receive_id)
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
