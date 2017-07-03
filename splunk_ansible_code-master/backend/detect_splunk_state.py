################################################
#
#    This is a tool intended to be used by Splunk Ops and splunk_ansible.py to report on the state of Splunk for a specified host
#    Typically, this script would be run before changing the Splunk state. For example, if splunk has stoped, then the user
#     may want to start. If splunk is running, then maybe the user needs to restart. Or stop.
#
###############################################


import argparse
import os
import time
import subprocess
import re

if __name__ == "__main__":

	# Parse arguments   
	parse = argparse.ArgumentParser(usage='%(prog)s hostname', description='Detect Splunk state on the specified host')
	parse.add_argument('hostname', nargs=1, help='The name of the host.')
	args = parse.parse_args()
	hostname = args.hostname[0]

	cwd = os.getcwd()

	# Look for a splunk instance
	command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo -u splunk /var/directory/splunk/bin/splunk status']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout)

	if "command not found" in str(stdout):
		splunk_status = "Does not exist"
	elif "LICENSE AGREEMENT" in str(stdout):
		splunk_status = "Stopped. Requires license acceptance to start again."
	else:
		splunk_status = str(stdout)


        # Look for a splunkforwarder instance
        command = ['ssh','-o','StrictHostKeyChecking=no',hostname,'sudo -u splunk /var/directory/splunkforwarder/bin/splunk status']
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        #print str(stdout)

        if "command not found" in str(stdout):
                splunkforwarder_status = "Does not exist"
	elif "LICENSE AGREEMENT" in str(stdout):
                splunkforwarder_status = "Stopped. Requires license acceptance to start again."
        else:
                splunkforwarder_status = str(stdout)

	splunk_status = splunk_status.replace("\n"," ")
	splunk_status = splunk_status.replace("\r","")
	splunkforwarder_status = splunkforwarder_status.replace("\n"," ")
	splunkforwarder_status = splunkforwarder_status.replace("\r","")
	print "splunkforwarder="+splunkforwarder_status
	print "splunk="+splunk_status

	exit()

