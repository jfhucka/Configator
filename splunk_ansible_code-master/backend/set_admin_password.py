##################
#
#   WARNING. THIS SCRIPT CONTAINS SENSITIVE SPLUNK PASSWORD INFORMATION and
#   SHOULD NOT FOUND IN THE WILD.
#
#################

import argparse
import os
import time
import subprocess

evolved_splunk_passwords = ['changeme','shoelaces66','turnBuckle1019']

if __name__ == "__main__":

        parse = argparse.ArgumentParser(usage='%(prog)s hostname splunk_path', description='Set the admin passwaord for the specified splunk instance on the specified host')
        parse.add_argument('hostname', nargs=1, help='The name of the host to apply Splunk configs. e.g. myhost.snc1')
	parse.add_argument('splunk_path', nargs=1, help='The oath the the Splunk instance. e.g. /var/directory/splunk')
        args = parse.parse_args()
        target_hostname = args.hostname[0]
	splunk_path = args.splunk_path[0]

	# Make sure the .splunk directory exists and is writable for svc_ansible
	#sudo mkdir /home/svc_ansible/.splunk
	command = ['ssh',target_hostname,'sudo mkdir /home/svc_ansible/.splunk']
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout)
	#sudo chown svc_ansible:wheel /home/svc_ansible/.splunk
	command = ['ssh',target_hostname,'sudo chown svc_ansible:wheel /home/svc_ansible/.splunk']
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	#print str(stdout)
	#sudo chmod 777 /home/svc_ansible/.splunk
	command = ['ssh',target_hostname,'sudo chmod 777 /home/svc_ansible/.splunk']
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	#print str(stdout)

	# Repeat the above for /var/directory/splunkforwarder/.splunk
	command = ['ssh',target_hostname,'sudo mkdir /var/directory/splunkforwarder/.splunk']
        #print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        #print str(stdout)
        command = ['ssh',target_hostname,'sudo chown splunk:splunk /var/directory/splunkforwarder/.splunk']
        #print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #print str(stdout)
        command = ['ssh',target_hostname,'sudo chmod 777 /var/directory/splunkforwarder/.splunk']
        #print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #print str(stdout)

	i = 1
	for old_password in evolved_splunk_passwords:
		if i >= len(evolved_splunk_passwords):
			break
		else:
			new_password = evolved_splunk_passwords[i]
			i=i+1
		command = ['ssh',target_hostname,'sudo -u splunk '+splunk_path+'/bin/splunk edit user admin -password '+new_password+' -role admin -auth admin:'+old_password]
		print str(command)
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout_cat, stderr = output.communicate()
		#print str(stdout_cat)

	if "User admin edited" in str(stdout_cat):
		print "Success"
	else:
		print "Fail"

	print str(evolved_splunk_passwords[-1])
		
