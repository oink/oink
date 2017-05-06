# -*- coding: utf-8 -*-
"""
This is the main program to run Supybot.
"""

import os
import sys
import signal

if sys.version_info < (2, 6, 0):
    sys.stderr.write('This program requires Python >= 2.6.0')
    sys.stderr.write(os.linesep)
    sys.exit(-1)

def _termHandler(signalNumber, stackFrame):
    raise SystemExit, 'Signal #%s.' % signalNumber

signal.signal(signal.SIGTERM, _termHandler)

import time
import optparse
import textwrap
import logging

started = time.time()

from smart_qq_bot.logger import logger

import supybot
import supybot.utils as utils
import supybot.registry as registry
import supybot.questions as questions

from supybot.version import version

def main():
    import supybot.conf as conf
    import supybot.world as world
    import supybot.drivers as drivers
    import supybot.schedule as schedule

    # We schedule this event rather than have it actually run because if there
    # is a failure between now and the time it takes the Owner plugin to load
    # all the various plugins, our registry file might be wiped.  That's bad.
    interrupted = False
    when = conf.supybot.upkeepInterval()
    schedule.addPeriodicEvent(world.upkeep, when, name='upkeep', now=False)
    world.startedAt = started
    while world.ircs:
        try:
            drivers.run()
        except KeyboardInterrupt:
            if interrupted:
                # Interrupted while waiting for queues to clear.  Let's clear
                # them ourselves.
                for irc in world.ircs:
                    irc._reallyDie()
                    continue
            else:
                interrupted = True
                log.info('Exiting due to Ctrl-C.  '
                         'If the bot doesn\'t exit within a few seconds, '
                         'feel free to press Ctrl-C again to make it exit '
                         'without flushing its message queues.')
                world.upkeep()
                import supybot.ircmsgs as ircmsgs
                for irc in world.ircs:
                    quitmsg = conf.supybot.plugins.Owner.quitMsg() or \
                              'Ctrl-C at console.'
                    irc.queueMsg(ircmsgs.quit(quitmsg))
                    irc.die()
        except SystemExit, e:
            s = str(e)
            if s:
                log.info('Exiting due to %s', s)
            break
        except:
            try: # Ok, now we're *REALLY* paranoid!
                log.exception('Exception raised out of drivers.run:')
            except Exception, e:
                print 'Exception raised in log.exception.  This is *really*'
                print 'bad.  Hopefully it won\'t happen again, but tell us'
                print 'about it anyway, this is a significant problem.'
                print 'Anyway, here\'s the exception: %s' % \
                      utils.gen.exnToString(e)
            except:
                print 'Man, this really sucks.  Not only did log.exception'
                print 'raise an exception, but freaking-a, it was a string'
                print 'exception.  People who raise string exceptions should'
                print 'die a slow, painful death.'
    now = time.time()
    seconds = now - world.startedAt
    log.info('Total uptime: %s.', utils.gen.timeElapsed(seconds))
    (user, system, _, _, _) = os.times()
    log.info('Total CPU time taken: %s seconds.', user+system)

def run():
    parser = optparse.OptionParser(usage='Usage: %prog [options] configFile',
                                   version='oink Supybot=%s' % version)
    parser.add_option('-P', '--profile', action='store_true', dest='profile',
                      help='enables profiling')
    parser.add_option('', '--debug', action='store_true', dest='debug',
                      help='Determines whether some extra debugging stuff '
                      'will be logged in this script.')

    (options, args) = parser.parse_args()
    if options.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if len(args) > 1:
        parser.error("""Only one configuration file should be specified.""")
    elif not args:
        parser.error(utils.str.normalizeWhitespace("""It seems you've given me
        no configuration file.  If you do have a configuration file, be sure to
        specify the filename.  If you don't have a configuration file, read
        docs/GETTING_STARTED and follow the instructions."""))
    else:
        registryFilename = args.pop()
        try:
            # The registry *MUST* be opened before importing log or conf.
            registry.open(registryFilename)
            import shutil
            shutil.copy(registryFilename, registryFilename + '.bak')
        except registry.InvalidRegistryFile, e:
            s = '%s in %s.  Please fix this error and start supybot again.' % \
                (e, registryFilename)
            s = textwrap.fill(s)
            sys.stderr.write(s)
            sys.stderr.write(os.linesep)
            raise
            sys.exit(-1)
        except EnvironmentError, e:
            sys.stderr.write(str(e))
            sys.stderr.write(os.linesep)
            sys.exit(-1)

    import supybot
    try:
        import supybot.log
    except supybot.registry.InvalidRegistryValue, e:
        # This is raised here because supybot.log imports supybot.conf.
        name = e.value._name
        errmsg = textwrap.fill('%s: %s' % (name, e),
                               width=78, subsequent_indent=' '*len(name))
        sys.stderr.write(errmsg)
        sys.stderr.write(os.linesep)
        sys.stderr.write('Please fix this error in your configuration file '
                         'and restart your bot.')
        sys.stderr.write(os.linesep)
        sys.exit(-1)
    global log
    log = supybot.log

    import supybot.conf as conf
    import supybot.world as world
    world.starting = True

    def closeRegistry():
        # We only print if world.dying so we don't see these messages during
        # upkeep.
        logger = log.debug
        if world.dying:
            logger = log.info
        logger('Writing registry file to %s', registryFilename)
        registry.close(conf.supybot, registryFilename)
        logger('Finished writing registry file.')
    world.flushers.append(closeRegistry)
    world.registryFilename = registryFilename

    networks = conf.supybot.networks()
    if not networks:
        questions.output("""No networks defined.  Perhaps you should re-run the
        wizard?""", fd=sys.stderr)
        # XXX We should turn off logging here for a prettier presentation.
        sys.exit(-1)

    # Stop setting our own umask.  See comment above.
    #os.umask(077)

    if not os.path.exists(conf.supybot.directories.log()):
        os.mkdir(conf.supybot.directories.log())
    if not os.path.exists(conf.supybot.directories.conf()):
        os.mkdir(conf.supybot.directories.conf())
    if not os.path.exists(conf.supybot.directories.data()):
        os.mkdir(conf.supybot.directories.data())
    if not os.path.exists(conf.supybot.directories.data.tmp()):
        os.mkdir(conf.supybot.directories.tmp())

    userdataFilename = os.path.join(conf.supybot.directories.conf(),
                                    'userdata.conf')
    # Let's open this now since we've got our directories setup.
    if not os.path.exists(userdataFilename):
        fd = file(userdataFilename, 'w')
        fd.write('\n')
        fd.close()
    registry.open(userdataFilename)

    import supybot.drivers as drivers
    import supybot.plugins.Owner as Owner
    import SmartQQAdapter
    SmartQQAdapter.newDriver = drivers.newDriver
    SmartQQAdapter.debug = options.debug
    drivers.newDriver = SmartQQAdapter.newDriverForSupybot

    owner = Owner.Class()

    if options.profile:
        import profile
        world.profiling = True
        profile.run('main()', 'oink-%i.prof' % time.time())
    else:
        main()

# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
