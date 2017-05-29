# -*- coding: utf-8 -*-

import threading
import re

try:
    import socketserver
except ImportError:
    import SocketServer as socketserver

from qqbot.utf8logger import DEBUG, ERROR, EXCEPTION, INFO
from qqbot.mainloop import StartDaemonThread, Put
from qqbot.common import Queue

class IrcException(Exception):
    pass

class IrcQuit(IrcException):
    pass

class IrcError(IrcException):
    pass

SRV_NAME    = "QQBotToIRCAdapter"
SRV_PREFIX  = "qq.bot"
_SRV_PREFIX = ':' + SRV_PREFIX
SRV_VERSION = "0.1"
SRV_WELCOME = "Welcome to %s v%s" % (SRV_NAME, SRV_VERSION)

RPL_WELCOME          = '001'
ERR_NOSUCHNICK       = '401'
ERR_NOSUCHCHANNEL    = '403'
ERR_CANNOTSENDTOCHAN = '404'
ERR_UNKNOWNCOMMAND   = '421'
ERR_ERRONEUSNICKNAME = '432'
ERR_NICKNAMEINUSE    = '433'
ERR_NEEDMOREPARAMS   = '461'

class IRCRequestHandler(socketserver.StreamRequestHandler):
    crlf = "\r\n".encode("utf8")

    def setup(self):
        socketserver.StreamRequestHandler.setup(self)

        self.nick = None
        self.realname = None
        self.password = None
        self.me = None
        self.isSupported = {}
        self.initialJoinPending = True
        self.lineProcessor_ = self.processLine_unregistered
        self.senderQueue = Queue.Queue()

        self.fetch_cv = threading.Condition()
        self.fetch_result = None

        self.server.addClient(self)

        reader = threading.Thread(target=self.reader)
        reader.daemon = True
        reader.start()

    def handle(self):
        self.sender()

    def finish(self):
        self.server.removeClient(self)
        socketserver.StreamRequestHandler.finish(self)
        INFO("finish()")

    def exit(self):
        INFO("exit()")
        self.sender_exit()
        self.reader_exit()

    def fetcher_(self, fetcher, *args, **kwargs):
        self.fetch_cv.acquire()
        try:
            self.fetch_result = (fetcher(*args, **kwargs), None)
        except Exception as e:
            self.fetch_result = (None, e)
        finally:
            self.fetch_cv.notify()
            self.fetch_cv.release()

    def fetch(self, fetcher, *args, **kwargs):
        Put(self.fetcher_, fetcher, *args, **kwargs)

        self.fetch_cv.acquire()
        self.fetch_cv.wait()
        (result, exception) = self.fetch_result
        self.fetch_result = None
        self.fetch_cv.release()

        if exception:
            raise exception
        return result

    def reader(self):
        try:
            while self.rfile:
                line = self.rfile.readline().strip().decode('utf8')
                if len(line) == 0:
                    break
                self.sender_put(self.processLine, line)
        finally:
            INFO("reader thread exit")
            self.sender_exit()

    def reader_exit(self):
        INFO("reader_exit()")

    # sender
    def sender(self):
        try:
            while True:
                try:
                    (f, args, kwargs) = self.senderQueue.get()
                    f(*args, **kwargs)
                finally:
                    self.senderQueue.task_done()

        except SystemExit:
            pass
        finally:
            INFO("sender thread exit")
            self.reader_exit()

    def sender_put(self, f, *args, **kwargs):
        self.senderQueue.put((f, args, kwargs))

    def sender_exit(self):
        def exit():
            raise SystemExit()
        self.sender_put(exit)

    def ircmsg(self, *args):
        args = list(args)
        if args[0]:
            args[0] = ':' + args[0]
        else:
            args[0] = _SRV_PREFIX
        if len(args) >= 3:
            args[-1] = ':' + args[-1]
        self.sendLine(' '.join(args))

    def sendLine(self, line):
        def sendLine(line):
            encoded = line.encode('utf8') if not isinstance(line, bytes) else line
            self.request.sendall(encoded)
            self.request.sendall(self.crlf)
        self.sender_put(sendLine, line)

    def processLine(self, line):
        if ' :' in line:
            (args, last) = line.split(' :', 1)
            args = args.split(' ')
            args.append(last)
        else:
            args = line.split(' ')

        try:
            self.lineProcessor_(*args)
        except IrcQuit as e:
            INFO("Client quiting %s" % e)
            self.sendLine("ERROR :Closing Link: %s (Client Quit)\r\n" % str(self.client_address))
            self.exit()
        except IrcError as e:
            INFO("ERROR %s" % e)
            self.sendLine("ERROR :%s\r\n" % e)
            self.exit()
        except Exception as e:
            EXCEPTION("failed to handle: %s" % ' '.join(args))
            self.sendLine("ERROR :%s\r\n" % e)

    def processLine_unregistered(self, command, *args):
        handler = getattr(self, 'do%s_' % command.upper(), None)
        if not handler:
            ERROR("unknown command: %s %s" % (command, ' '.join(args)))
            return
        try:
            handler(*args)
        except IrcException:
            raise
        except TypeError as e:
            EXCEPTION(e)
            self.ircmsg(None, ERR_NEEDMOREPARAMS, '*', command, "Not enough parameters" + str(e))

    def processLine_registered(self, command, *args):
        handler = getattr(self, 'do' + command.upper(), None)
        if not handler:
            self.ircmsg(None, ERR_UNKNOWNCOMMAND, self.nick, command, "Unknown command")
            return

        try:
            handler(*args)
        except IrcException:
            raise
        except TypeError as e:
            EXCEPTION(e)
            self.ircmsg(None, ERR_NEEDMOREPARAMS, self.nick, command, "Not enough parameters")

    def doPASS_(self, password):
        self.password = password

    def doNICK_(self, nick):
        self.nick = nick
        if self.realname is not None:
            self.register()

    def doUSER_(self, email, mode, unused, realname):
        # ignore args unless QQ api allow setting these values
        self.realname = realname
        self.id = self.server.bot.conf.qq
        if self.nick is not None:
            self.register()

    def doQUIT_(self, *args):
        raise IrcQuit(*args)

    def doPING_(self, *args):
        self.ircmsg(None, 'PONG', *args)

    def doPONG_(self, arg):
        pass

    def register(self):
        if self.password is None:
            raise IrcError("Password invalidate")
        self.lineProcessor_ = self.processLine_registered
        self.me = self.server.buildHostmask(self.nick, self.id)
        self.ircmsg(None, RPL_WELCOME, self.nick, SRV_WELCOME)
        self.ircmsg(None, '004', self.nick, SRV_PREFIX, 'qqbot', 'i', 'b', 'n')
        self.ircmsg(None, '005', self.nick,
                "CHANTYPES=#&",
                "PREFIX=" + self.server.IsSupported_prefix,
                "NETWORK=SmartQQ",
                "CHARSET=UTF-8",
                "NAMESX",
                "are supported by this server")
        self.ircmsg(None, '376', self.nick, 'End of MOTD command.')

    def doNICK(self, nick):
        oldme = self.me
        self.nick = nick
        self.me = self.server.buildHostmask(self.nick, self.id)
        self.ircmsg(oldme, "NICK", self.nick)

    def doPING(self, *args):
        self.ircmsg(None, 'PONG', *args)

    def doPONG(self, arg):
        pass

    def doMODE(self, *args):
        pass

    def joinPart(self, channels, isJoin):
        validChannels = self.fetch(
            lambda: [channel for channel in channels if self.server.findGroupByChannel(channel)]
        )
        nxChannels = set(channels) - set(validChannels)
        for channel in nxChannels:
            if isJoin:
                self.ircmsg(None, '403', self.nick, channel, 'No such channel')
            else:
                self.ircmsg(self.me, 'PART', channel)
        for channel in validChannels:
            self.ircmsg(self.me, 'JOIN', channel)
            self.doTOPIC(channel)
            self.doNAMES(channel)

    def doPROTOCTL(self, *protos):
        for proto in protos:
            self.isSupported[proto.upper()] = True

    def doPART(self, channels, reason=None):
        self.joinPart(channels.split(','), False)

    def joinAll(self):
        channels = self.fetch(
            lambda: ['#' + group.qq for group in self.server.bot.List("group")]
        )
        self.joinPart(channels, True)

    def doJOIN(self, channels, key=None):
        if self.initialJoinPending:
            self.initialJoinPending = False
            self.joinAll()
        self.joinPart(channels.split(','), True)

    def doTOPIC(self, channel, topic=None):
        group = self.fetch(lambda: self.server.findGroupByChannel(channel))
        if group:
            topic = group.nick + ' | ' + group.mark + ' | '+ group.gcode
            self.ircmsg(None, '332', self.nick, channel, topic)
        else:
            self.ircmsg(None, '403', self.nick, channel, 'No such channel')

    def memberName(self, member):
        return self.nick if member.qq == self.id else member.name

    def doNAMES(self, channel):
        prefix = (':%s 353 %s @ %s :' % (SRV_PREFIX, self.nick, channel)).encode('utf8')
        namesBuffer = prefix

        namesx = "NAMESX" in self.isSupported
        for member in self.fetch(lambda: self.server.findMembersByChannel(channel)) or []:
            if member.qq == '#NULL':
                continue

            hostmask = self.server.roleToPrefix[member.role_id]
            if namesx:
                hostmask += self.server.buildHostmask(self.memberName(member), member.qq)
            else:
                hostmask += self.server.toIrcNick(self.memberName(member))
            hostmask = hostmask.encode('utf8')

            if len(namesBuffer) + len(hostmask) + 1 >= 500:
                self.sendLine(namesBuffer)
                namesBuffer = prefix
            if len(namesBuffer) > len(prefix):
                namesBuffer += b' '
            namesBuffer += hostmask

        if len(namesBuffer) >= len(prefix):
            self.sendLine(namesBuffer)

        self.ircmsg(None, '366', self.nick, channel, 'End of /NAMES list.')

    def doWHO(self, target):
        if target.lower() == self.nick.lower():
            self.ircmsg(None, '352', self.nick, '*',
                    self.id, 'qq.com', SRV_PREFIX, self.nick,
                    'HrB', '%d %s' % (0, self.realname))
        elif target.startswith('#'):
            channel = target
            for member in self.fetch(lambda: self.server.findMembersByChannel(channel)) or []:
                self.ircmsg(None, '352', self.nick, channel,
                        member.qq, 'qq.com', SRV_PREFIX, self.server.toIrcNick(self.memberName(member)),
                        'Hr' + self.server.roleToPrefix[member.role_id], '0 .')
        self.ircmsg(None, '315', self.nick, target, 'End of /WHO list.')

    def doUSERHOST(self, *args):
        for user in args:
            if args == self.nick:
                self.ircmsg(None, '302', self.nick, self.buildHostmask(self.nick, self.id))

    def doQUIT(self, *args):
        self.ircmsg(self.nick, "QUIT", "Client Quit")
        raise IrcQuit(*(args[:1]))

    def doPRIVMSG(self, targets, content):
        return self.message(False, targets, content)
    def doNOTICE(self, targets, content):
        return self.message(True, targets, content)

    def message(self, isNotice, targets, content):
        if content.startswith("\x01") and content.endswith("\x01"):
            content = content[1:-1]
            if ' ' in content:
                ctcpType, content = content.split(' ', 1)
                if ctcpType != 'ACTION':
                    return 1
                content = '* ' + content
        if isNotice:
            content = 'NOTICE: ' + content

        content = self.server.stripColorCode(content)

        for targetName in set(targets.split(',')):
            if targetName.startswith('#'):
                target = self.fetch(lambda: self.server.findGroupByChannel(targetName))
            elif targetName.startswith('&'):
                target = None
            else:
                target = self.fetch(lambda: self.server.findBuddy(targetName))
            if not target:
                self.ircmsg(None, ERR_NOSUCHNICK, self.nick, targetName, 'No such nick/channel')
                continue
            self.server.bot.SendTo(target, content)

    newLineRegex = re.compile("[\r\n]+")
    def onQQMessage(self, contact, member, content):
        if contact.qq == '#NULL':
            ERROR("missing contact.qq for message %s" % content)
            return

        if member is not None:
            if member.qq == '#NULL':
                ERROR("missing member.qq for message %s" % content)
                return
            hostmask = self.server.buildHostmask(member.name, member.qq)
            target = '#' + contact.qq
        else:
            hostmask = self.server.buildHostmask(contact.qq, contact.qq)
            target = self.me

        for line in self.newLineRegex.split(content):
            self.ircmsg(hostmask, 'PRIVMSG', target, line)

class IRCServer(socketserver.ThreadingTCPServer):
    IsSupported_prefix = "(qo)~@"
    roleToPrefix = ['~@', '@', '', '']

    def __init__(self, bot, address):
        self.daemon_threads = True
        self.allow_reuse_address = True
        self.bot = bot
        self.clients = set()
        socketserver.ThreadingTCPServer.__init__(self, address, IRCClient)

    def addClient(self, client):
        self.clients.add(client)

    def removeClient(self, client):
        self.clients.remove(client)

    def onQQMessage(self, contact, member, content):
        for client in self.clients:
            client.onQQMessage(contact, member, content)

    def findGroupByChannel(self, channel):
        if not channel or not channel.startswith('#'):
            return
        channel = channel[1:]
        if not channel.isdigit():
            return
        group = self.bot.List("group", channel)
        if len(group) != 1 or group[0].qq == '#NULL':
            return
        return group[0]

    def findMembersByChannel(self, channel):
        group = self.findGroupByChannel(channel)
        if group:
            return self.bot.List(group)

    def findBuddy(self, guin):
        if not guin or not guin.isdigit():
            return
        buddy = self.bot.List("buddy", guin)
        if len(buddy) != 1 or buddy[0].qq == '#NULL':
            return
        return buddy[0]

    def findBuddyByHostmask(self, hostmask):
        return self.findBuddy(self.hostmaskToGuin(hostmask))

    def hostmaskToGuin(self, hostmask):
        if '!' not in hostmask:
            return
        hostmask = hostmask.split('!', 1)[1]
        if '@' not in hostmask:
            return
        return hostmask.split('@', 1)[0]

    invalidNickChars = { ord(c): '_' for c in '# 　\t!~@$'}
    def toIrcNick(self, nick):
        return str(nick).translate(self.invalidNickChars)

    def buildHostmask(self, nick, guin):
        nick = self.toIrcNick(nick)
        return "%s!%s@qq.com" % (nick, guin)

    colorRegex = re.compile(r'\x03[0-9]{1,2}(?:,[0-9]{1,2})?') # color
    hiddenRegex = re.compile(r'\x030,0.*') # color white,white
    colorModeRegex = re.compile(r'\x03|\x02|\x16|\x1F|\x1D') # color, bold, reverse, underline, italics
    def stripColorCode(self, content):
        content = self.hiddenRegex.sub('', content)
        content = self.colorRegex.sub('', content)
        content = self.colorModeRegex.sub('', content)
        return content
