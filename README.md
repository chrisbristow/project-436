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
Coming soon ....


include:           macosx_generic

file:              test.log
match:             bananas
active:            0123456;06:00-22:00,1;22:30-23:59
alert_all:         tags=TAG1  message=109 u

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
