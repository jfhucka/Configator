
#######
#
#   Usage:  python push_splunk_config.py (target_hostname)  (log_file_location)
#
#   This is the script that triggers a Splunk configuration push to the specified host
#
#   If the hostname (push target) is not specified as an arguement to this script, then
#   then host running this script is assummed to be the target host for the Splunk config update.
#
#   If the log file directory is not specified on the command line, then default LOG_FILE_LOCATION
#   is used in its stead.
#
######

# The host that pushes the Splunk configs
PUSH_SERVER = "ansible-control2.snc1"
PORT = 8098

# Default location for logging the response from the push server.
LOG_FILE_LOCATION = "/var/directory/log"

import socket
import sys
import time

# The host to be updated is the host specified on the command line OR the host running this script.
if (len(sys.argv) == 3):
	target_hostname = str(sys.argv[1])
else:
	target_hostname = socket.gethostname()

# The directory that contains the splunk.log file may be specified on teh command line
if (len(sys.argv) == 3):
	log_file_dir = str(sys.argv[2])
else:
	log_file_dir = LOG_FILE_LOCATION
	

#  Contact the push server with the name of the target host
try:
	s= socket.socket()
	s.connect((PUSH_SERVER,PORT))
except:
	print "ERROR.  Not able to connect to "+PUSH_SERVER
	exit()

try:
	s.sendall(target_hostname)
except:
	print "ERROR. Not able to send "+target_hostname+" to the server "+PUSH_SERVER
	ack = "ERROR. Not able to send "+target_hostname+" to the server "+PUSH_SERVER

try:
	ack1 = s.recv(1024)
except:
	print "ERROR. Did not get an acknowledgment from "+PUSH_SERVER
	ack1 = "ERROR. Did not get an acknowledgment from "+PUSH_SERVER

try:
        ack2 = s.recv(10240)
except:
        print  "ERROR. Did not get any new config push data from "+PUSH_SERVER
        ack2 = "ERROR. Did not get any new config push data from "+PUSH_SERVER


#  Log the feedback from the push server on the target host
log_file_name = log_file_dir+"/splunk.log"
try:
	log_file = open(log_file_name,"a")
	log_file.write("\n======= "+time.strftime("%Y-%m-%d %H:%M:%S")+" =======\n")
	log_file.write(str(ack1)+"\n")
	log_file.write(str(ack2)+"\n")
	log_file.close()
except:
	print "ERROR.  Not able to write to "+log_file_name

s.close()
exit()

