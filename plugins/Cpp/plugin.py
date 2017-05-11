###
# Copyright (c) 2002-2004, Jeremiah Fincher
# Copyright (c) 2010,2015 James McCoy
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

import time
import re

import supybot.conf as conf
import supybot.utils as utils
import supybot.world as world
from supybot.commands import *
import supybot.irclib as irclib
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
from supybot.utils.structures import MultiSet, TimeoutQueue

class Cpp(callbacks.PluginRegexp):
    callBefore = ['Dunno']
    addressedRegexps = ['matchCode', 'cpp']
    unaddressedRegexps= ['matchCodeChecked']

    def __init__(self, irc):
        self.__parent = super(Cpp, self)
        self.__parent.__init__(irc)

    def enable(self, irc, msg, args, channel):
        """[<channel>]

        enable cpp feature on channel
        """
        self.registryValue('channels').add(channel)
        irc.replySuccess()
    enable = wrap(enable, ['channel'])

    def disable(self, irc, msg, args, channel):
        """<channel>

        Ceases relaying between the channel <channel> on all networks.  The bot
        will part from the channel on all networks in which it is on the
        channel.
        """
        self.registryValue('channels').discard(channel)
        irc.replySuccess()
    disable = wrap(disable, ['channel'])

    def inFilter(self, irc, msg):
        if msg.command == 'PRIVMSG':
            replyTo = ircutils.replyTo(msg)
            if replyTo == "geordi" and irc.network == "FreeNode":
                (me, text) = msg.args
                self._replyIrc.queueMsg(callbacks.reply(self._replyMsg, text))
                print "ignored"
                return None
        return msg

    def _forwardRequest(self, irc, msg, code):
        freeNode = world.getIrc("FreeNode")
        if not freeNode:
            irc.reply("not connected to geordi yet")
            return

        irc.noReply()
        self._replyIrc = irc
        self._replyMsg = msg

        freeNode.queueMsg(ircmsgs.privmsg("geordi", code))

    def matchCode(self, irc, msg, match):
        r"^(<<.*|\{.*\}.*)$"
        print "matchcode"
        self._forwardRequest(irc, msg, callbacks.addressed(irc.nick, msg))

    def matchCodeChecked(self, irc, msg, match):
        (channel, text) = msg.args
        print "matchcode"
        if irc.isChannel(channel):
            if channel not in self.registryValue('channels'):
                return
        self._forwardRequest(irc, msg, text)
    matchCodeChecked.__doc__ = matchCode.__doc__

    def cpp(self, irc, msg, match):
        r"^(?:cpp|c\+\+) (.*)$"
        self._forwardRequest(irc, msg, cpp_regex.match(msg.args[1]).group(1))
    cpp_regex = re.compile(cpp.__doc__)

Class = Cpp

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
