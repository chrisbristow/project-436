# aa436.py
#
# This is the Agent for Project 436.  An instance of aa436.py runs
# on every host to be monitored.  After an aa436.py Agent is started it will:
# - Listen for UDP "I am here" broadcast notifications from ax436.py Servers.
# - Request configuration from the first ax436.py Server that it finds.
# - Commence monitoring for:
#   o Pattern matches in log files.
#   o Processes not running.
#   o System resource limit breaches (eg. disk space, inode usage, memory, load)
# - The aa436.py Agent will send regular heartbeat messages to the ax436.py Server
#   (if idle).
# - Reset and re-load its configuration if told to do so by the ax436.py Server.

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
import subprocess
import logging
import logging.handlers
from socket import *




# Globals:
# This list includes shared lists of log files to check, processes to monitor,
# the queue of updates to sent to the server etc.

file_consumer_list = []
host_name = os.uname()[1]
ps_command = []
process_list = []
uid_seed = 0
alert_queue = []
cmd_list = []
logger = logging.getLogger(__name__)




# Return True if current time is within range
# given in active_string (format: day_numbers;HH:MM-HH:MM, ...).

def is_active(active_string):
  if(len(active_string) == 0):
    actv = True

  else:
    actv = False
    ltm = time.localtime()

    for t in active_string.split(','):
      tmt = re.match('^([0-9]+);(\d+):(\d+)\-(\d+):(\d+)$', t)

      if tmt:
        if(((ltm[3] * 60) + ltm[4]) >= ((int(tmt.group(2)) * 60) + int(tmt.group(3))) and ((ltm[3] * 60) + ltm[4]) <= ((int(tmt.group(4)
) * 60) + int(tmt.group(5)))):
          if(tmt.group(1).find(str(ltm[6])) > -1):
            actv = True

  return(actv)



# An instance of file_consumer is created for each file
# tracking configuration.

class file_consumer:
  def __init__(self, filename, matches, actions):
    global logger

    self.open = False
    self.filename = filename
    self.seek = 2
    self.matches = matches
    self.tags = actions['tags']
    self.message = ''
    self.active = ''

    logger.info('Creating file consumer for file '+filename+' (patterns: '+str(matches)+', '+str(actions)+')')

    if('message' in actions):
      self.message = actions['message']

    self.period = 0

    if('period' in actions):
      self.period = int(actions['period'])

    self.threshold = 0

    if('threshold' in actions):
      self.threshold = int(actions['threshold'])

    self.count = 0
    self.next_report = time.time() + self.period

    self.metric = 0

    if('metric' in actions):
      self.metric = int(actions['metric'])

    if('active' in actions):
      self.active = actions['active']



  # Logs when a file consumer is closed down - this happens when
  # an aa436.py Agent receives a Reset command from the ax436.py Server.

  def __del__(self):
    self.fd.close()
    logger.info('Removing file consumer for file '+self.filename)



  # Checks to see if any of the "periodic" file events
  # need to be raised.  Examples of periodic events for files are:
  # - A count of the number of matches of a set of strings within a time period.
  # - An event raised if no instances of a specified string have appeared in a
  #   log file within a time period.

  def check_period(self):
    if(self.period > 0):
      if(time.time() > self.next_report):

        # Alert if matches exceed the threshold.
        if(self.threshold > 0 and self.count > self.threshold and len(self.message) > 0):
          self.list = self.list + [ self.tags + '%%' + self.filename + '%%' + self.message ]

        # Alert if no matches within n seconds.
        elif(self.count == 0 and len(self.message) > 0 and self.threshold == 0):
          self.list = self.list + [ self.tags + '%%' + self.filename + '%%' + self.message ]

        # Output the count of matches every n seconds.
        elif(len(self.message) == 0):
          self.list = self.list + [ self.tags + '%%' + self.filename + '%%' + str(self.count) ]

        self.next_report = time.time() + self.period
        self.count = 0




  # The main program calls read() for each file tracker.  Returns
  # a list of events from the do_read() function if within an active
  # time, otherwise returns an empty list.

  def read(self):
    if(is_active(self.active) == True):
      return(self.do_read())

    else:
      return([])




  # This function does the actual file reading.  Logic to deal with
  # log files "rolling" is contained here.

  def do_read(self):
    global logger

    self.list = []

    self.check_period()

    self.finished = False

    while(self.finished == False):
      if(self.open == False):
        try:
          self.st = os.stat(self.filename)
          self.inode = self.st.st_ino
          self.fd = open(self.filename)
          self.fd.seek(0, self.seek)
          self.open = True
          self.seek = 0
  
        except Exception:
          logger.error('Error: File '+self.filename+' not found')
          self.finished = True
  
      else:
        self.cp = self.fd.tell()
        self.nextline = self.fd.readline()
  
        if not self.nextline:
          try:
            self.st = os.stat(self.filename)
     
            if(self.st.st_ino != self.inode):
              self.fd.close()
              self.open = False
            else:
              self.fd.seek(self.cp)
              self.finished = True
  
          except Exception:
            logger.error('Error: File '+self.filename+' not found')
            self.finished = True
  
        else:
          for m in self.matches:
            if(re.search(m,self.nextline) is not None):
              if(self.period > 0):
                self.count += 1

              elif(len(self.message) > 0):
                # Alert every match with a pre-defined message.
                self.list = self.list + [ self.tags + '%%' + self.filename + '%%' + self.message ]

              else:
                # Alert every match with the actual line matched.
                self.list = self.list + [ self.tags + '%%' + self.filename + '%%' + self.nextline.strip() ]

    return(self.list)




# This function is called when an aa436.py Agent first receives configuation
# from an ax436.py Agent.

def do_config(conf):
  global file_consumer_list
  global ps_command
  global process_list
  global cmd_list
  global logger

  c_file = ''
  c_match = []
  c_active = ''
  c_process = ''

  logger.info('Configuration received from server')

  for cl in conf.split('%%'):
    m = re.match('^([a-z_:]+)\s+(.+)\s*$', cl)

    if m:
      cmd = m.group(1)
      arg = m.group(2)

      if(cmd == 'file:'):
        c_file = arg

      elif(cmd == 'match:'):
        c_match += [ arg ]

      elif(cmd == 'active:'):
        c_active = arg

      elif(cmd == 'alert_all:' and len(c_match) > 0 and len(c_file) > 0):
        am = re.match('^tags=(\S+)\s+message=(.+)\s*$', arg)

        if am:
          file_consumer_list += [ file_consumer(c_file, c_match, { 'tags': am.group(1), 'message': am.group(2), 'active': c_active }) ]

        else:
          am2 = re.match('^tags=(\S+)\s*$', arg)

          if am2:
            file_consumer_list += [ file_consumer(c_file, c_match, { 'tags': am2.group(1), 'active': c_active }) ]

        c_file = ''
        c_match = []
        c_active = ''

      elif(cmd == 'alert_n:' and len(c_match) > 0 and len(c_file) > 0):
        am = re.match('^tags=(\S+)\s+threshold=(\d+)\s+seconds=(\d+)\s+message=(.+)\s*$', arg)

        if am:
          file_consumer_list += [ file_consumer(c_file, c_match, { 'tags': am.group(1), 'threshold': am.group(2), 'period': am.group(3), 'message': am.group(4), 'active': c_active }) ]

        c_file = ''
        c_match = []
        c_active = ''

      elif(cmd == 'alert_count:' and len(c_match) > 0 and len(c_file) > 0):
        am = re.match('^tags=(\S+)\s+seconds=(\d+)\s*$', arg)

        if am:
          file_consumer_list += [ file_consumer(c_file, c_match, { 'tags': am.group(1), 'period': am.group(2), 'metric': '1', 'active': c_active }) ]

        c_file = ''
        c_match = []
        c_active = ''

      elif(cmd == 'alert_inactive:' and len(c_match) > 0 and len(c_file) > 0):
        am = re.match('^tags=(\S+)\s+seconds=(\d+)\s+message=(.+)\s*$', arg)

        if am:
          file_consumer_list += [ file_consumer(c_file, c_match, { 'tags': am.group(1), 'period': am.group(2), 'message': am.group(3), 'metric': '2', 'active': c_active }) ]

        c_file = ''
        c_match = []
        c_active = ''

      elif(cmd == 'ps_command:'):
        ps_command = arg.split()
        logger.info('Process check command: '+str(ps_command))

      elif(cmd == 'process:'):
        c_process = arg

      elif(cmd == 'alert_running:' and len(c_process) > 0):
        pc = re.match('^tags=(\S+)\s+min=(\d+)\s+max=(\d+)\s+message=(.+)\s*$', arg)

        if pc:
          pc_rec = { 'match': c_process, 'tags': pc.group(1), 'min': int(pc.group(2)), 'max': int(pc.group(3)), 'message': pc.group(4), 'count': 0, 'error': 0, 'active': c_active }
          process_list += [ pc_rec ]
          logger.info('Watching process: '+str(pc_rec))

        c_process = ''
        c_active = ''

      elif(cmd == 'run:'):
        cm = re.match('^command=(.+)\s+extract=(.+)\s*$', arg)

        if cm:
          new_cmd_list = { 'command': cm.group(1).strip().split(), 'extract': cm.group(2).strip(), 'alerts': [] }
          logger.info('Running command: '+str(new_cmd_list))
          cmd_list.append(new_cmd_list)

      elif(cmd == 'alert_if:'):
        cm = re.match('^tags=(\S+)\s+match=(\d+),(\S+)\s+upper_limit=(\d+),([0-9\.]+)\s+message=(.+)\s*$', arg)

        if cm:
          new_cmd_alist = { 'tags': cm.group(1), 'match_n': int(cm.group(2)), 'match_str': cm.group(3), 'upper_limit_n': int(cm.group(4)), 'upper_limit_v': float(cm.group(5)), 'message': cm.group(6), 'active': c_active }
          logger.info('Alerting on command output: '+str(new_cmd_alist))
          cmd_list[len(cmd_list)-1]['alerts'].append(new_cmd_alist)
          c_active = ''

        cm = re.match('^tags=(\S+)\s+match=(\d+),(\S+)\s+lower_limit=(\d+),([0-9\.]+)\s+message=(.+)\s*$', arg)

        if cm:
          new_cmd_alist = { 'tags': cm.group(1), 'match_n': int(cm.group(2)), 'match_str': cm.group(3), 'lower_limit_n': int(cm.group(4)), 'lower_limit_v': float(cm.group(5)), 'message': cm.group(6), 'active': c_active }
          logger.info('Alerting on command output: '+str(new_cmd_alist))
          cmd_list[len(cmd_list)-1]['alerts'].append(new_cmd_alist)
          c_active = ''

      elif(cmd == 'alert_metric:'):
        cm = re.match('^tags=(\S+)\s+match=(\d+),(\S+)\s+metric=(\d+)\s*$', arg)

        if cm:
          new_cmd_alist = { 'tags': cm.group(1), 'match_n': int(cm.group(2)), 'match_str': cm.group(3), 'metric': int(cm.group(4)), 'active': c_active }
          logger.info('Publishing on command output: '+str(new_cmd_alist))
          cmd_list[len(cmd_list)-1]['alerts'].append(new_cmd_alist)
          c_active = ''





# This function is called to erase all current configuration if the aa436.py Agent is
# sent a Reset command by the ax436.py Server.

def do_unconfig():
  global logger
  global file_consumer_list
  global ps_command
  global process_list
  global cmd_list

  logger.info('Unconfiguring')

  file_consumer_list = []
  ps_command = []
  process_list = []
  cmd_list = []





# This function is called to add a new alert to the alert queue.
# Alerts are sent to the ax436.py Server one by one.  Each has
# to be acknowleged before the next is sent.

def queue_alert(alert):
  global uid_seed
  global alert_queue
  global logger

  if(len(alert_queue) < 256):
    logger.info(time.ctime()+' Queueing: '+alert)

    uid = '{0}_{1}'.format(int(time.time()), uid_seed)
    uid_seed += 1
    alert_queue += [ [ uid, alert, 0, int(time.time()) ] ]

  else:
    logger.info(time.ctime()+' Alert not queued (queue full): '+alert)




# This is the main program loop.  UDP sockets are initialised and then
# a loop is entered which invokes log file checks, process checks etc.
# as well as receiving commands from the ax436.py Server.

def main(port):
  global process_list
  global alert_queue
  global logger
  global host_name
  global cmd_list

  logger.setLevel(logging.DEBUG)
  logger.addHandler(logging.handlers.RotatingFileHandler('aa436.log', maxBytes = 1000000, backupCount = 4))

  logger.info(time.ctime())
  logger.info('Listening on port '+str(port))
  logger.info('Server on port '+str(port + 1))

  server_name = ''
  server_seen = 0
  server_seen_timeout = 30
  configured = False
  last_config_req = 0
  last_update = time.time()
  idle_time = 67
  alert_queue = []
  process_check_interval = 20
  next_process_check = int(time.time()) + process_check_interval
  stats_check_interval = 60
  next_stats_check = int(time.time()) + stats_check_interval
  last_process_event = 0

  addr = ('', port)
  ad_sock = socket(AF_INET, SOCK_DGRAM)
  ad_sock.bind(addr)

  inputs = [ ad_sock ]
  outputs = []

  while(True):
    readable, writable, exceptional = select.select(inputs, outputs, inputs, 1.0)

    for rs in readable:
      udp_data = rs.recv(65536)
      m = re.match('^([A-Z]+)%%(.+)', udp_data.decode())

      if m:
        cmd = m.group(1)
        arg = m.group(2)

        if(cmd == 'SRVHB'):
          if(arg == server_name):
            server_seen = time.time()

          if(len(server_name) == 0):
            server_name = arg
            logger.info('Selected server: '+arg)

        elif(cmd == 'CONFIG'):
          do_config(arg)
          configured = True

        elif(cmd == 'RESET'):
          if(arg == host_name):
            do_unconfig()
            last_config_req = time.time() + 10
            configured = False

        elif(cmd == 'ACK'):
          if(arg == alert_queue[0][0]):
            del alert_queue[0]

    if(server_seen > 0 and time.time() > (server_seen + server_seen_timeout)):
      logger.info('Deselected server: '+server_name)
      server_name = ''
      server_seen = 0

    if(configured == False and len(server_name) > 0 and time.time() > (last_config_req + 10)):
      last_config_req = time.time()
      logger.info('Requesting configuration from '+server_name+' on port '+str(port+1))
      ad_sock.sendto(('CONFREQ%%'+os.uname()[1]).encode(), (server_name, port+1))
      last_update = time.time()

    if(server_seen > 0 and time.time() > (last_update + idle_time) and len(alert_queue) < 3):
      queue_alert('SYSTEM%%NULL%%Idle')
      last_update = time.time()

    for fc in file_consumer_list:
      for alert in fc.read():
        queue_alert(alert)

    if(len(ps_command) > 0 and int(time.time()) > next_process_check):
      ps_output = subprocess.check_output(ps_command)

      for zeroing_idx in range(len(process_list)):
        process_list[zeroing_idx]['count'] = 0

      for ps_line in ps_output.decode().split('\n'):
        for watching_idx in range(len(process_list)):
          pm = re.search(process_list[watching_idx]['match'], ps_line)

          if pm:
            process_list[watching_idx]['count'] += 1

      for checking_idx in range(len(process_list)):
        if(process_list[checking_idx]['count'] < process_list[checking_idx]['min'] or process_list[checking_idx]['count'] > process_list[checking_idx]['max']):
          process_list[checking_idx]['error'] += 1

        else:
          process_list[checking_idx]['error'] = 0

        if(process_list[checking_idx]['error'] > 1 and is_active(process_list[checking_idx]['active']) == True):
          process_alert_msg = process_list[checking_idx]['tags'] + '%%NULL%%' + process_list[checking_idx]['message'] + ' [' + str(process_list[checking_idx]['count']) + ']'
          queue_alert(process_alert_msg)
          process_list[checking_idx]['error'] = 0
          last_process_event = int(time.time())

      next_process_check = int(time.time()) + process_check_interval

    if(time.time() > next_stats_check):
      for run_cmd in cmd_list:
        for cmd_output_line in subprocess.check_output(run_cmd['command']).decode().split('\n'):
          c_ext = re.search(run_cmd['extract'], cmd_output_line)

          if c_ext:
            for run_alist in run_cmd['alerts']:
              if('upper_limit_n' in run_alist and is_active(run_alist['active'])):
                if(run_alist['match_str'] == c_ext.group(run_alist['match_n']) and float(c_ext.group(run_alist['upper_limit_n'])) > run_alist['upper_limit_v']):
                  queue_alert(run_alist['tags']+'%%NULL%%'+run_alist['message'])

              elif('lower_limit_n' in run_alist and is_active(run_alist['active'])):
                if(run_alist['match_str'] == c_ext.group(run_alist['match_n']) and float(c_ext.group(run_alist['lower_limit_n'])) < run_alist['lower_limit_v']):
                  queue_alert(run_alist['tags']+'%%NULL%%'+run_alist['message'])

              elif('metric' in run_alist and is_active(run_alist['active'])):
                if(run_alist['match_str'] == c_ext.group(run_alist['match_n'])):
                  queue_alert(run_alist['tags']+'%%NULL%%'+str(c_ext.group(run_alist['metric'])))

      next_stats_check = int(time.time()) + stats_check_interval

    if(last_process_event > 0 and time.time() > (last_process_event + (process_check_interval * 2) + 30)):
      last_process_event = 0
      queue_alert('SYSTEM%%NULL%%Process check: All clear')

    if(len(alert_queue) > 0):
      if(int(time.time()) > alert_queue[0][2]):
        ad_sock.sendto(('ALERT%%'+host_name+'%%'+alert_queue[0][0]+'%%'+str(alert_queue[0][3])+'%%'+alert_queue[0][1]).encode(), (server_name, port+1))
        alert_queue[0][2] = int(time.time()) + 10
        last_update = time.time()




# Start hook.  The only argument an aa436.py Agent takes is the UDP
# port to listen for broadcasts from the ax436.py Server on.

if __name__ == '__main__':
  if len(sys.argv) < 2:
    print('Usage: aa436.py udp_port')
    exit(1)

  else:
    main(int(sys.argv[1]))
