###
# Copyright (c) 2005, Jeremiah Fincher
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

import supybot.conf as conf
import supybot.ircutils as ircutils
import supybot.registry as registry

def configure(advanced):
    from supybot.questions import output, expect, anything, something, yn
    conf.registerPlugin('Cpp', True)
    if yn('Would you like to serve cpp channels?'):
        channels = anything('What channels?  Separated them by spaces.')
        conf.supybot.plugins.Cpp.channels.set(channels)

class Ignores(registry.SpaceSeparatedListOf):
    List = ircutils.IrcSet
    Value = conf.ValidHostmask
    
class Networks(registry.SpaceSeparatedListOf):
    List = ircutils.IrcSet
    Value = registry.String

Cpp = conf.registerPlugin('Cpp')
conf.registerGlobalValue(Cpp, 'channels',
    conf.SpaceSeparatedSetOfChannels([], """Determines which channels the bot
        handle << and {} as cpp"""))


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
