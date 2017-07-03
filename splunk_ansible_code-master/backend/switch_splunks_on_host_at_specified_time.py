################################################
#
#    This is a tool intended to be used by Splunk Ops to aid in the switch over from SPLUNK to SPLUNKFORWARDER on a specific host
#    This script is used to setup a specified time when the script "switch_splunks_on_host.py" should be run
#
#    The reason why "switch_splunks_on_host.py" should be run at a specified time is to minimize redundant logging of files
#       if SPLUNKFORWARD is started and re-ingests the logs already ingested by SPLUNK.
#    Typically, the logs are rolled at the top of the hour. In which case, the SPLUNKFORWARDER should only start at the top of the hour.
#
#    Actions taken:
#      - create a crontab on this host to run switch_splunks_on_host.py at the specified time
#
#    The user provides the HH:MM as a command line arg to this script.  That gets transloated to a crontab line ...
#
#    * * * * * 
#    - - - - -
#    | | | | |
#    | | | | ----- Any day of the week
#    | | | ------- The existing month
#    | | --------- The existing day
#    | ----------- Hour (0 - 23) "HH as specified by the command line arguement"
#    ------------- Minute (0 - 59) "MM as specified by the command line arguement"
#
#    
#
###############################################


import argparse
import os
from datetime import datetime
import subprocess
import re
import uuid

if __name__ == "__main__":

	# Parse arguments   
	parse = argparse.ArgumentParser(usage='%(prog)s hostname switch_time action', description='Switch from running SPLUNK to SPLUNKFOWRDER on a specified host at a specified time HH:MM. move/nomove SPLUNK to /tmp.')
	parse.add_argument('hostname', nargs=1, help='The name of the host.')
	parse.add_argument('switch_time',nargs=1, help='The time to switch HH:MM')
	parse.add_argument('action',nargs=1, help='move or nomove the SPLUNK directory to /tmp')
	args = parse.parse_args()
	hostname = args.hostname[0]
	switch_time = args.switch_time[0]
	action = args.action[0]

	cwd = os.getcwd()

	#  Check the correct format of the switch_time
	switch_time_list = switch_time.split(":")
	if len(switch_time_list) != 2:
		print "ERROR. The switch_time command line arguement needs to be in the form HH:MM"
		exit()
	try:
		hour = int(switch_time_list[0])
		if (hour < 0) or (hour > 23):
			print "ERROR. The switch_time HH looks incorrect"
			exit()
		minute = int(switch_time_list[1])
		if (minute <0) or (minute > 59):
			print "ERROR. The switch_time MM looks incorrect"
			exit()
	except:
		print "ERROR. The switch_time command line arguement needs to be in the form HH:MM"
		exit()

	today = datetime.now()
	day = str(today.day)
	month = str(today.month)

	comment = "###### Added by switch_splunks_on_host_at_specified_time.py"
	cron_time = str(minute)+" "+str(hour)+" "+day+" "+month+" *"
	cron_string = cron_time+" python "+cwd+"/switch_splunks_on_host.py "+hostname+" "+action

	#command = ['sudo','crontab','-l']
	command = ['crontab','-l']
	ps = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	output = ps.communicate()[0]

	#  If \n at the end of the output, dont add another one
	output_1 = ""
	if len(output) > 0:
		output_1 = str(output)[-1]

	if output_1 == "\n":
		new_crontab = str(output)+"###### Added by switch_splunks_on_host_at_specified_time.py"
	else:
		new_crontab = str(output)+"\n###### Added by switch_splunks_on_host_at_specified_time.py"

	#  Always end the contab with a new line
	new_crontab = new_crontab+"\n"+cron_string+"\n"

	print "\n\nThe new crontab is ...."
	print new_crontab

	temp_file_name = "/tmp/"+hostname+"-"+str(today.second)
	print temp_file_name
	temp_file = file(temp_file_name,"w")
	temp_file.write(new_crontab)
	temp_file.close()

	#command = ['sudo','crontab',temp_file_name]
	command = ['crontab',temp_file_name]
	ps = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	output = ps.communicate()[0]
	#print str(output)

	os.remove(temp_file_name)

	exit()

