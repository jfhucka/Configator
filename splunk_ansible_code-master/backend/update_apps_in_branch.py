################################################
#
#    This is a python that pulls all the splunk apps from teh git:/splunk_apps repo
#
#    This script should be attached to a cron job, if the local repo branch is to be kept up to date.
#    Or this script can be executed manaully after the user has made a change to the splunk_apps master repo.
#    
#    It is assumed that this script can be called at multiples by many different users, including the a crontab.
#    It is important that "git pulls" do not overlap and are not too burdensome to the Ansible server.
#
#    Therefore ....
#       Any git pull, will be proceeded by a git pull lock.
#       And process must successfully apply the git pull lock before attempting a git pull.
#       Only one git pull lock can exist at any time.
#       If a git pull is attempted, but another git pull is in process, then wait until the current git pull is done.
#          ... if the somoeone else then sets a git repo lock, then exit, Effectively someone has done a git pull on your behalf
#       Git pull locks and git push locks can not coincide.
#
###############################################

#  Lock bit location relative to location of this script.
lockBitLocation = "lockDirectory"
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
        logFileName = "refresh_splunk_app_repo-"+timestamp

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
        f.write(timestamp+" Going to refresh the splunk_apps repo on this server.\n")


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
	parse = argparse.ArgumentParser(usage='%(prog)s ', description='Pull the latest splunk apps down from the splunk_apps repo')
	args = parse.parse_args()

	# Start a log file
	# Create a updating_apps_<time_millsecond>.lck token and wait for the host.lck tokens to drain.
	# Check for only one updating_apps token. If 2, then the latest wins. The earliest dies.
	# Pull splunk_apps configs to local repo.
	# Record the freshness date in a local file
	# Close log

	cwd = os.getcwd()
	cwd = "/var/directory/manage_splunk"
	logFile = start_logging(cwd)

	#  Create a time based  "updating_apps_*.lck" token
	time_marker = int(round(time.time() * 1000))
	lock_file_name = "updating_apps_"+str(time_marker)+".lck"
	lockDir = cwd+"/"+lockBitLocation
	lockFileFullPath_apps = lockDir+"/"+lock_file_name
	try:
		if not os.path.isdir(lockDir):
			os.makedirs(lockDir)
			if (debug): print "Created lock directory "+lockDir
		with open(lockFileFullPath_apps, "w") as f:
			f.write("")
			f.close()
			log_message(logFile,"Created a lock file "+lockFileFullPath_apps)
	except:
		if (debug): print "ERROR.  Not able to create "+lockFileFullPath_apps
		log_message(logFile,"ERROR.  Not able to create "+lockFileFullPath_apps)
		stop_logging(logFile)
		exit()

	# Wait for host .lck file to drain
	num_tries = 0
	lockFileFullPath = lockDir+"/[!updating_apps]*.lck"
	while (num_tries < 30):
                num_tries = num_tries+1
		host_lock_list = glob.glob(lockFileFullPath)
		#print "host_lock_list="+str(host_lock_list)
		#host_lock_list = [fn for fn in glob(lockFileFullPath) if not os.path.basename(fn).startswith("updating_apps")]
                if len(host_lock_list) > 0:
                        log_message(logFile,"INFO. Detected "+str(host_lock_list)+". Will wait 5 seconds for these hosts to finish being updated.")
                        if (debug): print "INFO. Hosts are being updated. Wait 5 seconds and try again."
                        time.sleep(5)
                else:
                        break
        if num_tries == 30:
                log_message(logFile,"ERROR. Can not proceed because hosts are STILL being updated.")
                if (debug): print "ERROR. Can not proceed because hosts are STILL being updated."
                stop_logging(logFile)
		os.remove(lockFileFullPath_apps)	
                exit()

	# Host lock files have drained.
	log_message(logFile,"INFO. Host lock files have drained.")
	#if (debug): print "Host lock files have drained."
	# splunk_ansible.py will not proceed until the updating_apps_ lck token is removed.

	# Look at the now current queue of updating_apps_<time_millsecond>.lck tokens
	# If this token is the earliest (or only token), then proceed.
	# If the token queue is > 1, then die, unless this token is the latest.
	lockFileFullPath_apps_all = lockDir+"/updating_apps_*.lck"
	lockFileFullPath_apps_all_list = glob.glob(lockFileFullPath_apps_all)
	log_message(logFile,str(lockFileFullPath_apps_all_list))
	#print "lockFileFullPath_apps_all_list="+str(lockFileFullPath_apps_all_list)
	earliest = False
	latest = False
	if len(lockFileFullPath_apps_all_list) == 1:
		# Only one detected .lock file
		earliest = True
	else:
		# Parse each lock file and see if this is earliest or latest
		earliest = True
		latest = True
		for item in lockFileFullPath_apps_all_list:
			other_time_stamp = re.search('updating_apps_(.+?).lck',item).group(1)
			other_time_stamp_int = int(other_time_stamp)
			if time_marker > other_time_stamp_int:
				earliest = False
			if time_marker < other_time_stamp_int:
				latest = False
		#  If earliest in list and list has more than one, then exit and letthe later proceed.
		if len(lockFileFullPath_apps_all_list) > 1 and earliest==True:
			log_message(logFile,"INFO. We have not started a repo refresh, and there appears to be a pending, later repo refresh request.. So bail on this request.")
			if (debug): print "INFO. Other pending requests. Bail."
			os.remove(lockFileFullPath_apps)
			stop_logging(logFile)
			exit()

	#print str(earliest)
	#print str(latest)
	log_message(logFile,"earliest="+str(earliest)+" latest="+str(latest))
	if (earliest==True) or (latest==True):
		# Pull down the latest splunk_apps 
		#command = 'cd '+cwd+'/splunk_apps; /usr/local/bin/git pull'
		#print command
		#log_message(logFile,str(command))
		#output=subprocess.check_output(command, shell=True)
		#   git --git-dir=/var/directory/manage_splunk/splunk_apps/.git --work-tree=/var/directory/manage_splunk/splunk_apps pull
                command = ['/usr/local/bin/git','--git-dir=/var/directory/manage_splunk/splunk_apps/.git','--work-tree=/var/directory/manage_splunk/splunk_apps','pull','--no-edit']
		#command = ['/bin/sh','-c','"cd /var/directory/manage_splunk/splunk_apps && /usr/local/bin/git pull -q origin master"']
		#command = ['ssh','-o','StrictHostKeyChecking no','ansible-control2.snc1','cd /var/directory/manage_splunk/splunk_apps && /usr/local/bin/git pull']
                #if (debug): print str(command)
		log_message(logFile,str(command))
		try:
                	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                	stdout, stderr = output.communicate()
			#if (debug): print str(stdout)
			log_message(logFile,str(stdout))
		except Exception,e:
			log_message(logFile,"ERROR.  "+str(e))
			stop_logging(logFile)
			os.remove(lockFileFullPath_apps)
			exit()
		log_message(logFile,"INFO. Refreshed splunk_apps")
		if (debug): print "INFO. Refreshed splunk_apps"
		os.remove(lockFileFullPath_apps)
		stop_logging(logFile)
		exit()

	
