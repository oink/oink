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
        self.server = IRCServer(self)

    def onQQMessage(self, contact, member, content):
        self.server.onQQMessage(contact, member, content)

    def onStartupComplete(self):
        StartDaemonThread(self.server.serve_forever)

if __name__ == '__main__':
    RunBot(QQBotToIRCAdapter, None, "qqbot")
