# -*- coding: utf-8 -*-

import os
import sys

here = os.path.abspath(os.path.dirname(__file__))
sys.path.append(here)

from IRCServer import IRCServer

from qqbot import QQBot, RunBot
from qqbot.mainloop import StartDaemonThread

class QQBotToIRCAdapter(QQBot):
    def __init__(self):
        super(QQBot, self)
        self.server = None

    def onQQMessage(self, contact, member, content):
        content = content.replace('&lt;', '<')
        content = content.replace('&gt;', '>')
        if self.server:
            self.server.onQQMessage(contact, member, content)

    def onStartupComplete(self):
        ip, port = (self.conf.IRCServerAddress.split(':', 1) + [6667])[0:2]
        self.server = IRCServer(self, (ip, int(port)))
        StartDaemonThread(self.server.serve_forever)

if __name__ == '__main__':
    RunBot(QQBotToIRCAdapter)
