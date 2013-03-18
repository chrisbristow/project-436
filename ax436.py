# ax436.py
#
# This is the Server for Project 436.  It's main functions are:
# - Broadcasting "I am here" notifications to the local LAN so that
#   Project 436 Agents (aa436.py) can find it.
# - Supplying Agents with their configurations, on demand.
# - Sending Agents "Reset" commands if their configuration files
#   are updated.
# - Checking whether configured Agents have supplied a heartbeat
#   notification back to the Server recently.
# - Capture and acknowledgement of fault / metric events from
#   Agents.

# Copyright (c) 2013, Chris Bristow
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.



import sys
import os
import time
import re
import select
import string
import logging
import logging.handlers
from socket import *




# Main program.  The Server initialises it's log files (one for
# general log items and the other for it's Event Stream), reads
# and parses it's configuration file, sets up it's various UDP
# sockets and then enters a loop.  The loop processes commands
# and events from Agents as well as monitoring Agent configuration
# files - if a configuration file is updated, then the Agent
# the file refers to is notified ("Reset") so that it can
# re-initialise itself.

def main(conf_file):
  # This is the time after which an Agent is considered
  # "dead" if that Agent doesn't send any notifications
  # to the Server.
  max_idle_time = 180

  # Initialise the general Server log - ax436.log.
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.DEBUG)
  logger.addHandler(logging.handlers.RotatingFileHandler('ax436.log', maxBytes = 1000000, backupCount = 4))

  logger.info(time.ctime())

  # Read and parse the Server's configuration file.
  f = open(conf_file)

  for cf in f:
    if cf.startswith('port:'):
      tokens = cf.split()
      port = int(tokens[1])

    elif cf.startswith('broadcast:'):
      tokens = cf.split()
      bcaddr = tokens[1]

    elif cf.startswith('hosts:'):
      tokens = cf.split()
      host_dir = tokens[1]

    elif cf.startswith('includes:'):
      tokens = cf.split()
      include_dir = tokens[1]

    elif cf.startswith('event_stream:'):
      tokens = cf.split()
      event_stream_name = tokens[1]

  f.close()

  logger.info('Server broadcasting on port '+str(port)+' to '+bcaddr)
  logger.info('Agent channel on port '+str(port + 1))
  logger.info('Host configurations in '+host_dir)
  logger.info('Additional configurations in '+include_dir)
  logger.info('Event stream is '+event_stream_name)

  # Initialise the Server's event stream log file.
  event_logger = logging.getLogger('ax436_event_logger')
  event_logger.setLevel(logging.DEBUG)
  event_logger.addHandler(logging.handlers.RotatingFileHandler(event_stream_name, maxBytes = 1000000, backupCount = 4))

  addr = ('', port + 1)
  send_addr = (bcaddr, port)

  ad_sock = socket(AF_INET, SOCK_DGRAM)
  ad_sock.bind(addr)
  ad_sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

  inputs = [ ad_sock ]
  outputs = []

  # The Agent configuration folder is scanned every [scan_interval] seconds
  # to check for Agent configuration file changes.
  scan_interval = 10
  next_scan = time.time() + scan_interval

  # "I am here" broadcasts are sent every [i_am_here] seconds.
  i_am_here_interval = 5
  next_i_am_here = time.time() + i_am_here_interval

  scan_hash = {}

  while(True):
    readable, writable, exceptional = select.select(inputs, outputs, inputs, 1.0)

    for rs in readable:
      ( udp_data, from_addr ) = rs.recvfrom(65536)
      m = re.match('^([A-Z]+)%%(.+)', udp_data)

      if m:
        cmd = m.group(1)
        arg = m.group(2)

        # Respond to a "Configuration Requested" command from an Agent.
        if(cmd == 'CONFREQ'):
          logger.info('Received configuration request from '+arg)

          clines = 'START'

          try:
            logger.info('Loading host file '+host_dir+"/"+arg)

            cfile = open(host_dir+"/"+arg)
  
            for c in cfile:
              inc = re.match('^include:\s+(\S+)\s*$', c)
  
              if inc:
                logger.info('Loading include file '+include_dir+"/"+inc.group(1))

                ifile = open(include_dir+"/"+inc.group(1))
  
                for i in ifile:
                  clines += '%%'+i.strip()
  
                ifile.close()
  
              else:
                clines += '%%'+c.strip()
  
            cfile.close()

            logger.info('Sending configuration for '+arg+' on port '+str(port))
  
            ad_sock.sendto('CONFIG%%'+clines, (from_addr[0], port))

          except IOError:
            logger.info('Error: Unable to return configuration for host '+arg)

        # Respond to an Event sent to the Server by an Agent.
        elif(cmd == 'ALERT'):
          event_logger.info(time.ctime()+'%%'+arg)
          ss = string.split(arg,'%%')
          ad_sock.sendto('ACK%%'+ss[1], (from_addr[0], port))

          if(ss[0] in scan_hash):
            scan_hash[ss[0]]['agent_seen'] = int(time.time())

    # Broadcast an "I am here" heartbeat message.
    if(time.time() > next_i_am_here):
      ad_sock.sendto('SRVHB%%'+os.uname()[1], send_addr)
      next_i_am_here = time.time() + i_am_here_interval

    # Scan the host configuration folder for changes.
    if(time.time() > next_scan):
      for sh in os.listdir(host_dir):
        sst = os.stat(host_dir+'/'+sh)

        if(sh not in scan_hash):
          scan_hash[sh] = { 'agent_seen': 0, 'mtime': int(sst.st_mtime) }
          logger.info('New host configuration: '+sh)

        elif(scan_hash[sh]['mtime'] != int(sst.st_mtime)):
          logger.info('Host configuration '+sh+' has been updated')
          scan_hash[sh]['mtime'] = int(sst.st_mtime)
          ad_sock.sendto('RESET%%'+sh, send_addr)

        if((int(time.time()) - scan_hash[sh]['agent_seen']) > max_idle_time):
          event_logger.info(time.ctime()+'%%'+sh+'%%000000%%'+str(int(time.time()))+'%%SYSTEM%%NULL%%Host is inactive')

      next_scan = time.time() + scan_interval




# Start hook.

if __name__ == '__main__':
  if len(sys.argv) < 2:
    print 'Usage: ax436.py configuration_file'
    exit(1)

  else:
    main(sys.argv[1])
