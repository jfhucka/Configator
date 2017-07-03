################################################
#
#    This is a tool that will be used everytime a user or admin want to change Splunk's current state on the given host.
#    Typically, this script would be executed everytime the hosts Splunk configs are changed, or a user/admin wants to
#        start, stop, restart, or boot on start.
#
#    Actions taken:
#         - SSH into the specified host
#         - perform the specified action on the Splunk instance
#      
#         Options:
#	      start
#	      stop
#             restart
#             boot-start
#             (basically .... anything!)
#
###############################################


import argparse
import os
import time
import subprocess
import re

logFileLocation = "logs"

#######
#
#  It should be assumed that multiple processes exist, all updating various hosts at the same time.
#  Therefore, logging to a single unified log is not supported.
#  So per-host-logfiles are created. Each log file is unique for a given host at a given time.
#  Log files are in a Splunk friendly format so that teh data can be easily ingested into Splunk.
#
######
def start_logging(cwd,hostname):

        #  Get the current time and create the log file
        timestamp = time.strftime("%Y%m%d%H%M%S")
        logFileName = hostname+"-"+timestamp

        logDir = cwd+"/"+logFileLocation
        logFileFullPath = logDir+"/"+logFileName

        if not os.path.isdir(logDir):
                os.makedirs(logDir)
                if(debug): print "Created log directory "+logDir
        if os.path.isfile(logFileFullPath):
                if(debug): print "ERROR. Log file exists."
                exit(0)
        else:
                try:
                        f = open(logFileFullPath, "w")
                except:
                        if (debug): print "ERROR.  Not able to open log file "+logFileFullPath
                        exit(0)

        #  Populate the logfile with an opening event ..
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(timestamp+" hostname="+hostname+"\n")

        return(f)

def log_message(logFile,message):

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        logFile.write(timestamp+" message='"+message+"'\n")
        return()

def stop_logging(fileHandle):

        #  Populate the logfile with an closing event ..
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        fileHandle.write(timestamp+" message=Stopped Logging.\n")
        fileHandle.close()

        return()


if __name__ == "__main__":

	# Parse arguments   
        #parse = argparse.ArgumentParser(usage='%(prog)s -hostname hostname -action action', description='Cause the specified action to be run on the specified host')
        #parse.add_argument('-hostname', nargs=1, help='The name of the host.')
        #parse.add_argument('-action',nargs=1, help='The Splunk command.')

	parse = argparse.ArgumentParser(usage='%(prog)s hostname action <splunk_type>', description='Cause the specified action to be run on the specified host')
	parse.add_argument('hostname', nargs=1, help='The name of the host.')
	parse.add_argument('action',nargs=1, help='The Splunk command.')
	parse.add_argument('splunk_type',nargs='?', help='Specify if this is "splunk" or a "splunkforwarder"')
	args = parse.parse_args()
	hostname_list = args.hostname
	action_list = args.action
	splunk_type_list = args.splunk_type

	if hostname_list == None:
		print "ERROR.  You need to specify a target host"
		exit()
	hostname = hostname_list[0]
	if action_list == None:
		print "ERROR.  You need to specify an action to take on "+hostname
		exit()
	action = action_list[0]
	if splunk_type_list == None:
		splunk_type = "splunkforwarder"
	else:
		splunk_type = splunk_type_list
		#print str(splunk_type_list)
		#print splunk_type
		if (splunk_type != "splunk") and (splunk_type != "splunkforwarder"):
			print "ERROR.  The splunk_type need be either 'splunk' or 'splunkforwarder'"
			exit()

	#print hostname
	#print action
	#print splunk_type

	cwd = os.getcwd()
	logFile = start_logging(cwd,hostname)

	command = ['ssh','-o','StrictHostKeyChecking no',hostname,'sudo -u splunk /var/directory/'+splunk_type+'/bin/splunk'+' '+action]
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	message = "/var/directory/splunk/bin/splunk stop ..."+stdout.replace("\n"," ")
	message_clean = message.replace("\r","")
	log_message(logFile,message_clean)
	print str(stdout)

	#  Detect ERROR: The mgmt port [8089] is already bound.  Splunk needs to use this port.  
	#    ....  and advise the user.
	if "Splunk needs to use this port" in str(stdout):
		print "  **************************************"
		print "  *  It appears that there is already  *"
		print "  *  an instance of Splunk running on  *"
		print "  *  this host. Best to SSH into the   *"
		print "  *  host and stop Splunk, before      *"
		print "  *  starting a new version of Splunk. *"
		print "  *                                    *"
		print "  *  Or run switch_splunks_on_host.py  *"
		print "  **************************************"

	stop_logging(logFile)	

	exit()

