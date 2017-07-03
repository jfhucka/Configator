
##########
#
#   This script runs continiously listening to the prescribed port 
#   When a hostname is sent to the port, this script triggers splunk_manage.py
#   For the specified host.
#
#########

###  TODO ...  Create log file and write activity to the log file.  Rotate log.

import time 
import socket
import subprocess
from thread import *

HOST = ''                # Symbolic name meaning all available interfaces
PORT = 8098              # The listening port
LOG_FILE_PATH = '/var/directory/manage_splunk/logs'

#
#   Spawn a thread when the script detects a port request to push configs to a specific host
#
def clientthread(conn,push_target_host_name):
	#  Let the client know we got the push request
	try:
        	c.send("Will push Splunk configs from "+str(socket.gethostname())+" to "+str(push_target_host_name))
        except:
        	print "ERROR.  Not able to send farewell message"
        	c.close()
		return()

	command = '/usr/local/bin/python /var/directory/manage_splunk/splunk_ansible.py '+push_target_host_name+' T'
	log_message(push_target_host_name,command)
        print command
        output=subprocess.check_output(command, shell=True)
	log_message(push_target_host_name,output)
	#print output
	c.sendall(output)
	c.close()
	log_message(push_target_host_name,"Connection with Ansible server is now closed.")
	print "Closed connection"

def log_message(push_target_host_name,message):

        file_timestamp = time.strftime("%Y%m%d")
        logFileName = "push_configs-"+file_timestamp	
	event_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
	command = 'echo "'+str(event_timestamp)+' '+push_target_host_name+' '+str(message)+'" >> '+LOG_FILE_PATH+'/'+logFileName
	#print command
	output=subprocess.check_output(command, shell=True)
	if len(str(output)) > 0:
		print "ERROR. Not able to log message to file"
	return()

if __name__ == "__main__":

	current_hostname = socket.gethostname()
	log_message(current_hostname,"Starting script to listen on port "+str(PORT))

	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		#  On case the port is blocked by a previous run of this script that crashed or was terminated.
		s.close()
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		#log_message(current_hostname,"Port "+str(PORT)+" was blocked on start. Closing port.")
	except:
		print "INFO:  Had to close socket before using it."	
		log_message(current_hostname,"Port "+str(PORT)+" open.")
		

	try:
		s.bind((HOST, PORT))
		log_message(current_hostname,"Bound to port "+str(PORT))
	except:
		log_message(current_hostname,"INFO: Not able to bind to port "+str(PORT))
		exit()

	s.listen(5)
	log_message(current_hostname,"Listening on port "+str(PORT))
	while True:
		c, addr = s.accept()
		log_message(current_hostname,"Got connection from "+str(addr))
		#print "Got connection from "+str(addr)
		try:
			hostname = socket.gethostbyaddr(addr[0])[0]
			#print "     =>"+str(hostname)
		except:
			#print "ERROR.  Got connection from unknown host."
			log_message(current_hostname,"ERROR.  Got connection from unknown host.")
			c.close()
			continue

		#  Get the incoming hostname. Note, the incoming hostname may be different from the connected host
		#  This would be true if a user on the Splunk UI selected a target host from a list.
		try:
			push_target_host_name = c.recv(1024)
			print "Pushed Target Host Name is "+str(push_target_host_name)
			log_message(current_hostname,"Request to push configs to "+str(push_target_host_name))
		except:
			print "ERROR.  Did not receive the target host name."
			log_message(current_hostname,"ERROR. Did not Did not receive the target host name. Terminating connection.")
			c.close()
			continue


		start_new_thread(clientthread, (c,push_target_host_name,))


