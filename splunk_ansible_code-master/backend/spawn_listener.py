#!/usr/local/bin/python
##########
#
#   This script spawns splunk_manager_listener.py to run in the background. The splunk_manager_listener process should persist
#   while the server is running and should be re-spawned have the server has restarted.
#
#   The spawned splunk_manager_listener.py script listens to a specific port. When a remote server hits that port, the 
#   splunk_manager_listener.py script builds and Ansible playbook fro that host and pushes Splunk configs.
#
#########


import subprocess
import argparse

if __name__ == "__main__":

	parse = argparse.ArgumentParser(usage='%(prog)s action', description='Spawn a background process that runs splunk_manager_listener.')
        parse.add_argument('action', nargs=1, help='start or stop or restart')
        args = parse.parse_args()
        action = args.action[0]

	#  Check to see if a splunk_manager_listener.py process is already running.
	listening = False
	cmd = "ps aux | grep splunk_manager_listener | grep -v grep"
	ps = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
	output = ps.communicate()[0]
	output_list = output.split("\n")
	for item in output_list:
		if "splunk_manager_listener" in item:
			#print str(item)
			item_list = item.split()
			process_id = item_list[1]
			#print "process id is "+process_id
			listening = True
			break

	if action == "start":
		if listening:
			print "ERROR.  Can not start splunk_manager_listener.py, because a splunk_manager_listener process already exists. See PID: "+process_id
		else:
			cmd = ['nohup','/usr/local/bin/python','/var/directory/manage_splunk/splunk_manager_listener.py','>','/tmp/listen_out','2>','/tmp/listen_err','<','/dev/null','&']
			subprocess.Popen(cmd)
	elif action == "stop":
		if listening:
			cmd = ['sudo','kill','-9',process_id]
			subprocess.Popen(cmd)
			print "Killed process "+process_id
		else:
			print "Hunh? No running process of splunk_manager_listener.py found."
	elif action == "restart":
		if listening:
			cmd = ['sudo','kill','-9',process_id]
			subprocess.Popen(cmd)
			cmd = ['nohup','/usr/local/bin/python','/var/directory/manage_splunk/splunk_manager_listener.py','>','/tmp/listen_out','2>','/tmp/listen_err','<','/dev/null','&']
			subprocess.Popen(cmd)
		else:
			cmd = ['nohup','/usr/local/bin/python','/var/directory/manage_splunk/splunk_manager_listener.py','>','/tmp/listen_out','2>','/tmp/listen_err','<','/dev/null','&']
			subprocess.Popen(cmd)
	elif action == "status":
		if listening:
			print "Process ID "+str(process_id)+" is listening"
		else:
			print "Not listening"
	else:
		print "ERROR.  I do not recognize the action '"+action+"'"


