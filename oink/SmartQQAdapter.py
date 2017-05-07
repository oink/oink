# -*- coding: utf-8 -*-

"""
Supybot driver adapter to SmartQQ
"""

import time
import logging

from threading import Thread
from supybot import (conf, drivers, ircmsgs)
from supybot.ircutils import isChannel

from smart_qq_bot.logger import logger
from smart_qq_bot.messages import (GroupMsg, PrivateMsg, DiscussMsg, KICK_MSG)
from smart_qq_bot.signals import (
    on_all_message,
    on_group_message,
    on_private_message,
    on_discuss_message,
)

import smart_qq_bot.main as smart_qq_bot_main

# origin one
newDriver = None
debug = False

def smart_qq_main():
    smart_qq_bot_main.main_loop(no_gui=True, debug=debug, http=True)

class SmartQQAdapter(drivers.IrcDriver, drivers.ServersMixin):
    def __init__(self, irc):
        self.msg_id = 0
        self.irc = irc
        self.bot = None
        drivers.IrcDriver.__init__(self, irc)
        drivers.ServersMixin.__init__(self, irc)
        self.msgs = []

        adapter = self
        @on_group_message(name='SmartQQAdapter[group]')
        def adapter_group_message(msg, bot):
            adapter.bot = bot
            adapter.adaptGroupMessage(msg)

        @on_private_message(name='SmartQQAdapter[private]')
        def adapter_private_message(msg, bot):
            adapter.bot = bot
            adapter.adaptPrivateMessage(msg)

    def run(self):
        time.sleep(conf.supybot.drivers.poll())
        while True:
            msg = self.irc.takeMsg()
            if msg is None:
                break
            try:
                method = getattr(self, "send_" + msg.command)
            except AttributeError:
                print "Unhandled " + unicode(msg)
                continue
            method(msg)
        while self.msgs:
            self.irc.feedMsg(self.msgs.pop())

    def connect(self, **kwargs):
        thread = Thread(target=smart_qq_main)
        thread.setDaemon(True)
        thread.start()

    def reconnect(self, wait=False, reset=True):
        pass

    def die(self):
        drivers.log.die(self.irc)

    def name(self):
        return '%s(%s)' % (self.__class__.__name__, self.irc)

    def send_NICK(self, msg):
        self.nick = msg.args[0]
        pass

    def send_USER(self, msg):
        self.connect()
        self.msgs.append(ircmsgs.IrcMsg('', "001", (self.nick, 'Welcome')))
        self.msgs.append(ircmsgs.IrcMsg('', "376", ('End of /MOTD command.', )))

    def send_PING(self, msg):
        self.msgs.append(ircmsgs.pong(msg.args[0]))

    def send_NOTICE(self, msg):
        self.send_PRIVMSG(msg)

    def send_PRIVMSG(self, msg):
        (target, content) = msg.args

        # ACTION
        if content.startswith('\x01') and content.endswith('\x01'):
            content = content[1:-1].split(' ', 1)
            if len(content) == 2 and content[0] == 'ACTION':
                content = '* ' + content[1]

        if isChannel(target):
            groupId = str(target[1:])
            groupCode = self.groupIdToCode[groupId]
            self.bot.send_group_msg(reply_content=content, group_code=groupCode, msg_id=self.msg_id)
        else:
            guid = str(target)
            uin = self.guidToUin[guid]
            self.bot.send_friend_msg(reply_content=content, uin=uin, msg_id=self.msg_id)
        self.msg_id += 1

    @staticmethod
    def toIrcNick(nick):
        return str(nick).translate(None, '# \t!@$')

    uinToGuid = {}
    guidToUin = {}
    groupIdToCode = {}
    def toPrefix(self, nick, uin, uidGetter):
        if uin in self.uinToGuid:
            guid = self.uinToGuid[uin]
        else:
            self.uinToGuid[uin] = guid = uidGetter()
            self.guidToUin[guid] = uin

        return "%s!%s@%s" % (nick or guid, guid, 'qq.com')

    def adaptGroupMessage(self, msg):
        uin = msg.send_uin
        nick = msg.src_sender_card and self.toIrcNick(msg.src_sender_card) or self.toIrcNick(msg.src_sender_name)
        prefix = self.toPrefix(nick, uin, lambda: msg.src_sender_id)

        groupId = str(msg.src_group_id)
        self.groupIdToCode[groupId] = msg.group_code

        msg = ircmsgs.privmsg('#' + groupId, msg.content, prefix);
        self.msgs.append(msg)

    def adaptPrivateMessage(self, msg):
        uin = msg.from_uin
        prefix = self.toPrefix(None, uin, lambda: self.bot.uin_to_account(uin))

        msg = ircmsgs.privmsg(self.nick, msg.content, prefix)
        self.msgs.append(msg)

def newDriverForSupybot(irc, moduleName=None):
    print "Driver for " + irc.network
    if irc.network == "SmartQQ":
        return SmartQQAdapter(irc)
    else:
        return newDriver(irc, moduleName)

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
