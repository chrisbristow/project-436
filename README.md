Project-436
===========
Overview
--------
Project 436 was formulated to deliver an ultra-lightweight distributed monitoring
framework for Unix-like systems.  It has a basic Supervisor-Observer design, uses
UDP for messaging between Agents (Observers) and Servers (Supervisors) and is written
in Python.

All configuration is held on the host (or hosts) running the Server process, so all
that has to be distributed to hosts to be monitored is the Agent code (one file) itself.

The Server (ax436.py)
---------------------
The Server's main functions are:

- Broadcasting "I am here" notifications to the local LAN so that
  Agents (aa436.py) can discover the Server's IP address.
- Supplying Agents with their configurations, on demand.
- Sending a "Reset" command to an Agent if that Agent's centrally-held
  configuration file is updated.
- Checking whether configured Agents have supplied a heartbeat
  notification back to the Server recently.
- Capture and acknowledgement of fault / metric events from
  Agents.
- Writing a stream of events from Agents to a file.

Multiple Servers can be run on the same LAN.  Agents will pick the
first Server instance that they see an "I am here" broadcast from for all
further Agent-Server interactions.  All Servers on a LAN are active 
and independent - there is no Active / Passive fault-tolerance configuration
required on the Servers.  All Servers need access to copies of all Agent configurations.

The ax436.py Server is supplied, on startup, with a single configuration
file containing details such as:

- The address and port to use for all UDP communications.
- The file name to stream incoming events into.
- Folders in which to find Agent configurations.

The Agent (aa436.py)
--------------------
The Agent process is supplied, on startup, with the port number on which
to listen for UDP Server "I am here" broadcasts.  After receiving such a broadcast
message, it will then request it's configuration from the ax436.py Server
which sent the broadcast.  Once the Server responds with the configuration
(which the Server obtains from local files, see above), the Agent will start
monitoring.  This monitoring consists of:

- Reading and pattern-matching in log files.  Matching can:
  - Return the actual line matched.
  - Return a configured string.
  - Return a count of matches within a specific period.
  - Return a string if no matches are found within a specific period.
- Checking for processes not running, or too many instances of a
  process running.  The Agent is supplied with a "ps" command to use
  for these checks.
- Periodically running commands in order to obtain information from
  a host such as:
  - Filesystem usage (free space and / or inode usage).
  - Load average.
  - Free memory.
- Commands run can generate events (based on thresholds), or report
  metrics.
- All monitoring operations can be provided with set of times when
  they should be "active".  This can be used, for instance, to ignore
  events that may be invoked during a system's maintenance period.

If an aa436.py Agent's configuration needs to be changed, it can be
instructed to discard it's current configuration by sending it a "Reset"
message.  The ax436.py Server does this if it detects that a configuration
file has been updated.  Once the aa436.py Agent has discarded it's
configuration, it requests it's configuration once again from the Server.

Quick Start
-----------
The following is a quick guide to getting up-and-running with 436.

Firstly, place the ax436.py program in a folder on the host which will
act as a Server.  The ax436.py Server also requires a configuration file
which contains the following directives:

- event_stream:    Incoming events are written to this file.
- port:            UDP port to broadcast to / respond to agents.
- broadcast:       Broadcast address to use for "i_am_here" notifications.
- hosts:           Folder in which to find agent host configuration files.
- includes:        Folder in which to find agent include configuration files.

For example, create a file, ax436.conf, containing:

  event_stream:     ax436_event_stream.log

  port:             9000

  broadcast:        10.10.10.255

  hosts:            hosts_436

  includes:         includes_436

Next, start the ax436.py Server as follows (specifying ax436conf as the Server configuration file):

  python ax436.py ax436.conf
  
The Server will write:

- General log information to ax436.log
- A stream of incoming events to ax436_event_stream.log
 
On each host where an aa436.py Agent process needs to run, place the aa436.py
Agent program and start it up as follows (specifying it's UDP comms port, in this case 9000):

  python aa436.py 9000

The Agent process will write a log to aa436.log.  Note that both the Server and Agent restrict
their log output using fixed-size rolling log files.

At this point, Agents have no configuration files, so will not be actively monitoring.  To enable
monitoring, a configuration file for each Agent will need to be created in the "hosts:"
folder (in this example, the "hosts_436" folder) on the host running the ax436.py Server.

Agent configuration directives are placed in groups within the file, with each group
capable of generating one or more events.  All events have "tags" associated with them
which event-processing applications can use to link events to systems / services, determine
priorities etc.  Tags are just strings (cannot contain spaces).

The directives which can be added to an Agent configuration file are shown below:

For file pattern matching:

- file: - specifies a log file to follow.
- match: - specifies a pattern to be matched in a log file.
- alert_all: - generate an event if any patterns in a file match - the event contains the log file
  line which matched, or overridden with a specific message.
- alert_n: - generate an event if more then a specific number of pattern-matches occur within a
  specified time period.
- alert_count: - generate an event containing a count of all matches within a specified time period.
- alert_inactive: - generate an event if no matches occur within a specified time period.

For process monitoring (the process table is checked every 40 seconds):

- process: - specifies a process name to monitor.
- alert_running: - specify the minimum and maximum instances, plus a message to log if the instance
  count is outside those bounds.
- ps_command: - specifies the command to use to obtain the process list (this is specified once per Agent).

For running other commands (eg. for disk space, inode usage, memory or load monitoring).  Commands
are run every 60 seconds:

- run: - specifies a command to run and text to extract from the command's output.
- alert_if: - generate an event if a metric within a command's output exceeds or falls short of a
  specified limit.
- alert_metric: - generate a metric event each time the command is run (every 60 seconds).

Generic directives:

- include: - include the contents of the specified file (from the "includes:" folder) in the configuration
  sent to an Agent.
- active: - specify that a monitoring directive should only produce events within a specific range of times.
  the format is a set of comma-separated strings, one for each day/time range.  Each string looks like:
  [day_of_week];HH:MM-HH:MM
  Eg, 0123456;12:00-14:00 means events will be generated between 12:00 and 14:00 any day of the week.
  06;09:00-17:00 means events will be generated between 09:00 and 17:00 on Saturdays and Sundays only.

Below are some examples of how Agent configuration directives can be used:

This generates an event for each line in test.log which contains the strings "pattern" or "two".  The
event contains the actual line in test.log which matched:

file:              test.log
match:             pattern
match:             two
alert_all:         tags=TESTING,FILES,LOW_PRIORITY

This generates an event for each line in test.log which contains the strings "pattern" or "two".  The
event contains the string "Got It":

file:              test.log
match:             pattern
match:             two
alert_all:         tags=TESTING,FILES,LOW_PRIORITY  message=Got It



file:              test.log
match:             \d+
alert_all:         tags=NUM1

file:              test.log
match:             the big one
alert_n:           tags=EVERY  threshold=2  seconds=10  message=too many matches

#file:              test.log
#match:             count it
#alert_count:       tags=COUNT  seconds=10

#file:              test.log
#match:             .
#alert_inactive:    tags=INACTIVE  seconds=10  message=too quiet

#file:              notfound.log
#match:             .
#alert_all:         tags=NOTFOUND_TEST

ps_command:        ps -fe

process:           vzxhead
active:            0123456;00:00-23:59
alert_running:     tags=PROCESS  min=0  max=0  message=Incorrect number of VZXs running

process:           /Applications/Minecraft.app/Contents/MacOS/JavaApplicationStub
alert_running:     tags=MINECRAFT  min=1  max=1  message=Minecraft is no longer running

#process:           /sbin/launchd
#alert_running:     tags=LAUNCHD  min=5  max=20  message=A minimum of five launchd processes should be running

#run:               command=df -i  extract=\s+([0-9\.]+)%\s+\d+\s+\d+\s+([0-9\.]+)%\s+(\S+)
#alert_if:          tags=FS  match=3,/  upper_limit=1,95  message=Filesystem / exceeded 95 pct space utilisation
#alert_if:          tags=FS  match=3,/  upper_limit=2,95  message=Filesystem / has used over 95 pct of its inodes
#alert_metric:      tags=FS_MET  match=3,/  metric=1

run:               command=uptime  extract=(\S+) averages:\s+([0-9\.]+)\s+
alert_if:          tags=LOAD  match=1,load  upper_limit=2,4  message=Load average is over 4
active:            0123456;00:00-21:00
alert_metric:      tags=LOAD_MET  match=1,load  metric=2

run:               command=vm_stat  extract=(\S+) free:\s+(\d+)
alert_metric:      tags=MEM  match=1,Pages  metric=2
