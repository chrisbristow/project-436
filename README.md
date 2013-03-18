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
  Agents (aa436.py) can find the Server's IP address.
- Supplying Agents with their configurations, on demand.
- Sending a "Reset" command to an Agent if that Agent's centrally-held
  configuration file is updated.
- Checking whether configured Agents have supplied a heartbeat
  notification back to the Server recently.
- Capture and acknowledgement of fault / metric events from
  Agents.
- Writing a stream of events from Agents to a file.

Multiple Servers can be run on the same LAN.  Agents will pick the
first Server instance they see an "I am here" broadcast from for all
further Agent-Server interactions.  All Servers on a LAN are active -
the is no concept of Active / Passive required.  This means that
all Servers need access to copies of all Agent configurations.

The ax436.py Server is supplied, on startup, with a single configuration
file which contains details such as:

- The address and port to use for all UDP communications.
- The file name to stream events into.
- Folders in which to find Agent configurations.

The Agent (aa436.py)
--------------------
The Agent process is supplied, on startup, with the port number on which
to listen for UDP "I am here" broadcasts.  After receiving such a broadcast
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
  process running.
