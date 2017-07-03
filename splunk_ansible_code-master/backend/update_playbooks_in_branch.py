################################################
#
#    This is a python that pushes all the ansible playbooks to the git:/splunk_playbooks repo
#
#    This script should be attached to a cron job, if the local repo branch is to be kept up to date.
#    Or this script can be executed manaully after the user has made a change to the splunk_apps master repo.
#    
#    It is assumed that playbooks are only pushed via this app. And that pushes do not overlap.
#    Therefore, no locks.
#
###############################################

logFileLocation = "logs"

debug=True

import argparse
import os
import time
import subprocess
import re
import glob
import shutil



def start_logging(cwd):

        #  Get the current time and create the log file
        timestamp = time.strftime("%Y%m%d%H%M%S")
        logFileName = "refresh_playbook_repo-"+timestamp

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
        f.write(timestamp+" Going to refresh the playbooks by pusshing up to the repo.\n")


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
	
	# Parse arguments   prog='splunk_ansible',
	parse = argparse.ArgumentParser(usage='%(prog)s ', description='Push the latest playbooks up to the repo')
	args = parse.parse_args()

	cwd = os.getcwd()
	cwd = "/var/directory/manage_splunk"
	logFile = start_logging(cwd)

	#  get the SSH_AUTH_SOCK env variable
	command = 'echo $SSH_AUTH_SOCK'
	output=subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
	sock = str(output).replace("\n","")
	#sock = "/tmp/ssh-SgMpRWg702/agent.702"
	#sock = "/tmp/ssh-GxrMiq1003/agent.1003"
	sock = "/tmp/ssh-MiHhx18390/agent.18390"
	print "The SSH_AUTH_SOCK is "+sock
	log_message(logFile,"The SSH_AUTH_SOCK is "+sock)

	# get the SSH_AGENT_PID
	command = 'ps -aux | grep agent'
	output=subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
	#print str(output)
	output_list = output.split("\n")
	for item in output_list:
		if "ssh-agent" in item:
			item_list = item.split()
			pid = item_list[1]
	#print "pid is "+pid
	pid = "18391"
	log_message(logFile,"The PID is "+pid)

	command = cwd+"/update_playbooks_in_branch.sh"
	#command = 'SSH_AUTH_SOCK='+sock+'; export SSH_AUTH_SOCK; SSH_AGENT_PID='+pid+'; export SSH_AGENT_PID; /usr/local/bin/git --git-dir=/var/directory/manage_splunk/splunk_playbooks/.git --work-tree=/var/directory/manage_splunk/splunk_playbooks push'
	#print command
	log_message(logFile,command)
	output=subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
	print str(output)
	log_message(logFile,"=>"+str(output)+"<=")

	log_message(logFile,"INFO. Refreshed splunk_apps")
	#if (debug): print "INFO. Refreshed splunk_apps"
	stop_logging(logFile)
	exit()

	
