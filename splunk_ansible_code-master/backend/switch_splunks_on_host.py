################################################
#
#    This is a tool intended to be used by Splunk Ops to aid in the switch over from SPLUNK to SPLUNKFORWARDER on a specific host
#    Typically, this script would be run once, after the Splunk FWDer has been initially installed and configured.
#
#    Actions taken:
#         - stop the SPLUNK forwarder
#         - start the SPLUNKFORWARDER
#         - have the SPLUNK FORWARDER start on boot
#         - move SPLUNK to /tmp/splunk.orig
#
###############################################


import argparse
import os
import time
import urllib2
import yaml
import subprocess
import re
import uuid
import glob
import shutil

logFileLocation = "logs"
debug = True

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
        logFileName = hostname+"-switch-"+timestamp

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


#
#  Make sure that the hostname ans servername on the target host matches the hostname specified in splunk ops config
#  Restart Splunk if name changed and Splunk is already running.
#
def ensure_hostname_is_correct(cwd,logFile,target_hostname,password,splunk_full_path):

        #python ./set_hostname.py splunk1-dev.snc1 /var/directory/splunkforwarder turnbuckle1019
        path_to_script = cwd+"/set_hostname.py"
        command = ['python',path_to_script,target_hostname,splunk_full_path,password]
        #log_message(logFile,str(command))
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        log_message(logFile,str(stdout))
        if (debug): print str(stdout)
        if "Success" in str(stdout):
                log_message(logFile,"INFO:  The hostname was changed.")
                if (debug): print "INFO:  The hostname was changed."
        else:
                log_message(logFile,"INFO:  The hostname was not changed.")
                if (debug): print "INFO:  The hostname was not changed."
		log_message(logFile,str(stdout))
		if (debug): print str(stdout)
        return()




#
#  Setting the password has been relegated to a separate script so tha passwords can be somewhat locked up in a private git repo.
#
def set_admin_password(cwd,logFile,target_hostname,splunk_full_path):

        path_to_script = cwd+"/set_admin_password.py"
        command = ['python',path_to_script,target_hostname,splunk_full_path]
        log_message(logFile,str(command))
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        #log_message(logFile,str(stdout))
        #if (debug): print str(stdout)
        if "Success" in str(stdout):
                log_message(logFile,"INFO:  The admin password was changed.")
                if (debug): print "INFO:  The admin password was changed."
        else:
                log_message(logFile,"INFO:  The admin password was not changed.")
                if (debug): print "INFO:  The admin password was not changed."

        stdout_list = stdout.split("\n")
        password = stdout_list[1].strip()

        return(password)


if __name__ == "__main__":

	# Parse arguments   
	parse = argparse.ArgumentParser(usage='%(prog)s hostname action', description='Switch from running SPLUNK to SPLUNKFOWRDER on a specified host.')
	parse.add_argument('hostname', nargs=1, help='The name of the host.')
	parse.add_argument('action',nargs=1, help='move or no_move the SPLUNK dir to /tmp')
	args = parse.parse_args()
	hostname = args.hostname[0]
	action = args.action[0]

	cwd = os.getcwd()
	cwd = "/var/directory/manage_splunk"
	logFile = start_logging(cwd,hostname)
	#log_message(logFile,"Hello")
	#stop_logging(logFile)
	#exit()

	#  Check to see if SPLUNK is running ...
	command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo -u splunk /var/directory/splunk/bin/splunk status']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	if "splunkd is not running" in str(stdout):
		print "SPLUNK is already switched over."
	else:
		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo -u splunk /var/directory/splunk/bin/splunk stop']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		message = "/var/directory/splunk/bin/splunk stop ..."+stdout.replace("\n"," ")
		log_message(logFile,message)
		print str(stdout)

		time.sleep(5)

		# While the "splunk" user is not attached to a process, change the splunk homr dir to SPLUNKFORWADER
		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo usermod -d /var/directory/splunkforwarder -m splunk']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		log_message(logFile,"Switched the splunk user home directory to splunkforwarder")
		log_message(logFile,str(stdout))
		print "usermod output =>"+str(stdout)+"<="
		if "currently used by process" in str(stdout):
			print "*******************"
			print "ERROR. Likely problem is that person is logged in to this host as the splunk user."
			print "       Not able to move splunk user until person logs out."
			print "       After splunk user logs out, need to manually execute sudo usermod -m -d /var/directory/splunkforwarder splunk"
			print "*******************"

		# Assume that is SPLUNK was just stooped  that SPLUNKFORWARDER needs to start ...
		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo -u splunk /var/directory/splunkforwarder/bin/splunk start --accept-license --answer-yes --no-prompt']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		message = "/var/directory/splunkforwarder start ..."+stdout.replace("\n"," ")
		log_message(logFile,message)
		print str(stdout)

		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo /var/directory/splunkforwarder/bin/splunk enable boot-start']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		message = "/var/directory/splunk/bin/splunk enable boot-start ..."+stdout.replace("\n"," ")
		log_message(logFile,message)
		print str(stdout)

		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo rm -rf /usr/local/etc/init.d/splunk_forwarder']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		message = "sudo rm -rf /usr/local/etc/init.d/splunk_forwarder"
		log_message(logFile,message)
		print str(stdout)

		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo ln -s /etc/init.d/splunk /usr/local/etc/init.d/splunk_forwarder']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		message = "ln -s /etc/init.d/splunk /usr/local/etc/init.d/splunk_forwarder"
		log_message(logFile,message)
		print str(stdout)

		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo rm -rf /etc/rc3.d/S*splunk']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		message = "rm -rf /etc/rc3.d/S90splunk"
		log_message(logFile,message)
		print str(stdout)

		# Make sure that admin password is set correctly
		splunk_full_path = "/var/directory/splunkforwarder"
                password = set_admin_password(cwd,logFile,hostname,splunk_full_path)

                # Make sure that hostname and servername are correct
                # Restart splunk if needed.
                ensure_hostname_is_correct(cwd,logFile,hostname,password,splunk_full_path)

	if action == "move":

        	#  Test to see if /tmp directory can hold the SPLUNK data
        	command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo df /']
        	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        	stdout, stderr = output.communicate()
        	stdout_list = stdout.split("\n")
        	stdout_words = stdout_list[1].split()
        	tmp_storage = int(stdout_words[3])
        	command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo du /var/directory/splunk -s']
        	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        	stdout, stderr = output.communicate()
        	stdout_words = stdout.split()
        	splunk_storage = int(stdout_words[0])
        	print str(tmp_storage),str(splunk_storage)
        	if tmp_storage > splunk_storage:
                	print "The /tmp directory can hold the splunk data"
        	else:
                	print "The /tmp directory can NOT the splunk data"

		# Check to make sure /tmp/splunk.orig does not already exist.
		command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo ls -l /tmp/splunk.orig']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		if "No such file" in str(stdout) :
			# The /tmp/splunk.orig doe snot exist, yet!
			print "Moving SPLUNK to /tmp/splunk.orig     This may take awhile."
			command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo mv -f /var/directory/splunk /tmp/splunk.orig']
			output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			stdout, stderr = output.communicate()
			message = "Moved old splunk to /tmp ... "+stdout.replace("\n"," ")
			log_message(logFile,message)
			print "Moved SPLUNK to /tmp"
			print str(stdout)

			# Check to make sure the SPLUNK directory is empty 
			command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo ls -1 /var/directory/splunk']
			output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			stdout, stderr = output.communicate()
			if len(stdout) == 0:
	
				#  Need to specifically remove the splunk directory
				command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo rm -rf /var/directory/splunk']
				output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                		stdout, stderr = output.communicate()
				log_message(logFile,"Deleted the /var/directory/splunk directory")
				print "Deleted the /var/directory/splunk directory"
			else:
				if "No such file" in str(stdout) :
					log_message(logFile,"The old SPLUNK dir was removed")
					print "The old SPLUNK dir was removed"
				else:
					log_message(logFile,"The old SPLUNK dir was not deleted. Looks like there is still data in SPLUNK")
					print "The old SPLUNK dir was not deleted. Looks like there is still data in SPLUNK"
		else:
			print "The /tmp/splunk.orig file alerady exists. And I do not advise overwritting it. ABORT!"

	stop_logging(logFile)	
	print ""
	print "sudo -u splunk bash"
        print "tail -f /var/directory/splunk/var/log/splunk/splunkd.log"
        print "tail -f /var/directory/splunkforwarder/var/log/splunk/splunkd.log"
        print "/var/directory/splunk/bin/splunk status"
        print "/var/directory/splunkforwarder/bin/splunk status"
        print ""


	exit()

