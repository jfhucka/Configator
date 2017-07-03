################################################
#
#    This is a tool intended to be used by Splunk Ops to aid in the FWDer migration to Ansible.
#
#    Given a sourcetype and Splunk search duration, this script returns a list of known hosts that send data to the sourcetype
#    Note, that ops-config can not be relied upon to get the host names, because the ops-config files to do not appear to be up to date.
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

if __name__ == "__main__":

	# Parse arguments   
	parse = argparse.ArgumentParser(usage='%(prog)s sourcetype search_window ', description='Get all the hosts that contribute to a specified sourcetype.')
	parse.add_argument('sourcetype', nargs=1, help='The name of the sourcetype')
	parse.add_argument('search_window', nargs=1, help='The Splunk search window. e.g. 1d DO NOT PUT A minus sign in front of this parameter.')
	args = parse.parse_args()
	sourcetype = args.sourcetype[0]
	search_window = args.search_window[0]

	#  Create a lock file to prevent more than one process working on the same host at the same time
	cwd = os.getcwd()

	#  Subcommand / curl to get the results
	#      ./get_hosts.sh production accertify -1h
	path_to_script = cwd+"/get_hosts.sh"
	command = [path_to_script,"production",sourcetype,"-"+search_window]
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
	stdout_list=stdout.split()


	#  output result into a file 
	#    python collect_configs.py splunk1-dev.snc1 
	path_to_output = cwd+"/host_list"
	path_to_python = cwd+"/collect_configs.py"
	f = open(path_to_output,"w")
	skip=1
	for item in stdout_list:
		if skip==1:
			if (len(item)==4) and (item[0]=='h') and (item[1]=='o') and (item[2]=='s') and (item[3]=='t'):
				skip=0
			continue
		new_item=item.replace('"','')
		f.write("python "+path_to_python+" "+new_item+"\n")

	f.close
	print "Done.  Check out the newly created file host_list"

	exit() 
