################################################
#
#    This is a tool intended to be used by Splunk Ops to aid in the breaking up of the MAIN index
#
#    Given a specific host, this script will :
#       1.  read the index.map file and create an internal mapping between sourcetype and index
#       2.  FInd all the inputs.conf file in the working Splunk instance
#       3.  scp all the inputs.conf files locally
#       4.  process all the inputs.conf files and change/insert the index=_____
#       5.  scp each inputs.conf back into its original directory.
#
###############################################


#  Lock bit location relative to location of this script.
lockBitLocation = "lockDirectory"
logFileLocation = "logs"
credential_name = "BreakMainSheet_credentials.json"

SCOPES = 'https://www.googleapis.com/auth/spreadsheets.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Sheets API Python Break Main'

debug=True

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
import httplib2

#  sudo pip install --upgrade google-api-python-client
from apiclient import discovery
from apiclient.discovery import build
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

#######
#
#  Setting the lock bit prevents the system from running two simulatanous process to update the same
#  host at the same time
#  Note:  This does not prevent against multiple Ansisble servers from accessing the same host. In which
#         case a lock bit must be set by the Ansible playbook on the taregt host.
#
#######
def set_lock(target_hostname, cwd):
	
	lockFileName = target_hostname+".lck"
	lockDir = cwd+"/"+lockBitLocation
	lockFileFullPath = lockDir+"/"+lockFileName
	if not os.path.isdir(lockDir):
		os.makedirs(lockDir)
		if (debug): print "Created lock directory "+lockDir

	if os.path.isfile(lockFileFullPath):
		if (debug): print "ERROR. Lock file exists. Host is already being updated."
		exit(0)
	else:
		with open(lockFileFullPath, "w") as f:
    			f.write("")
			f.close()

	return(lockFileFullPath)


#######
#
#  Remove the lock file so that other processes can update the same host
#
#######
def remove_lock(lockFileFullPath):

        try:
		os.remove(lockFileFullPath)
		if (debug): print "Lock file removed"
        except:
		if (debug): print "ERROR. Not able to remove the lock file: "+lockFileFullPath
		exit(0)
	

def stop_logging(fileHandle):

        #  Populate the logfile with an closing event ..
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        fileHandle.write(timestamp+" message=Stopped Logging.\n")
	fileHandle.close()

        return()









######
#
#  Check that another process is not pushing or pulling down configs form the splunk git production repo
#  If local bit is already set, then wait until unlocked.
#  When unlocked, immediately set the lock bit with a unique guid name. Check that this process got the lock and then move on ....
#
#####
def check_set_repo_lock(cwd):


	j=0
	while j<10 :

       		lockFileName_wildcard = "git_repo*.lck"
       		lockDir = cwd+"/"+lockBitLocation
       		lockFileFullPath_wildcard  = lockDir+"/"+lockFileName_wildcard
		id = uuid.uuid1()
		lockFileName = "git_repo_"+str(id)+".lck"
		lockFileFullPath  = lockDir+"/"+lockFileName 

		i = 0
		x = glob.glob(lockFileFullPath_wildcard)
       		while i<100 and len(x)>0:
       			time.sleep(5)
			x = glob.glob(lockFileFullPath_wildcard) 
               		if (debug): print "Waiting for git_repo.lck bit to be cleared."
			i=i+1
		if i==100:
			if (debug): print "git_repo.lck bit never cleared."
			exit(0)

       		with open(lockFileFullPath, "w") as f:
			f.write("")
			f.close()

		# Check to make sure that we got the lock
		if os.path.isfile(lockFileFullPath):
			if (debug): print("Created repo lock file "+lockFileFullPath)
			return(lockFileFullPath)
		else:
			j=j+1


	if (debug): print "Giving up. Not able to create lock file."
	exit(0)


def get_splunk_home(cwd,target_hostname):

	#  Find all the instances of Splunk in the /var/directory/ directory.
	#  Try and get a "running" responce from any one of those instances.

	#  ssh splunk1-dev.snc1 'ls -1 /var/directory/splunk*/bin/splunk'
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'ls -1 /var/directory/splunk*/bin/splunk']
        if (debug): print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()	
	splunk_lines = stdout.split()
	for item in splunk_lines:
		command = ['ssh',target_hostname,'sudo '+item+' status']
		#if (debug): print str(command)
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        	stdout, stderr = output.communicate()
		status_split = stdout.split("\n")
		if "splunkd is running" in status_split[0]:
			segments = item.split("/")
			splunk_home = "/"+segments[1]+"/"+segments[2]+"/"+segments[3]+"/"
			return(splunk_home)
	return("")



def scp_input_files(cwd,target_hostname,splunk_home,whoiam):

	#  Find all the "inputs.conf" files in the Splunk working directory
	#  cp the inputs.conf tile to "/tmp/etc-system-local-inputs.conf and chown to the users name
	#  scp all the files down to the local machine

        command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo find '+splunk_home+'etc -name inputs.conf']
        #print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        splunk_lines = stdout.split()
	#print str(splunk_lines)

	#  Create a directory on the host computer to hold all the inputs.conf file
	command = ['ssh',target_hostname,'mkdir /tmp/inputs_repo']
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout)

	#  Put all the inputs.conf files into /tmp/inputs_repo
	dst_list = []
	for input_file in splunk_lines:
		if splunk_home in input_file:
			dst_filename = input_file.replace("/","_")
			dst_path = "/tmp/inputs_repo/"+dst_filename
			dst_list.append(dst_path)
			command = ['ssh',target_hostname,'sudo cp '+input_file+' '+dst_path]
			#print str(command)
			output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			stdout, stderr = output.communicate()
			#print str(stdout)
	
	#  Chown the /tmp/inputs_repo so that is readable
	command = ['ssh',target_hostname,'sudo chown -R '+whoiam+":"+whoiam+" /tmp/inputs_repo"]
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout)

	#  Make local inputs_repo to hold the incoming inputs.conf file
	command = ['mkdir',cwd+"/inputs_repo"]
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout)

	#  scp the files inputs.conf files from the host into the local inputs_repo
	command = ['scp',target_hostname+":/tmp/inputs_repo/*",cwd+"/inputs_repo"]
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout)

	print "All inputs.conf downloaded to local repo "+cwd+"/inputs_repo"

	return(True)
		


def process_local_input_files(cwd,target_hostname,splunk_home,whoiam,index_map):

	#  Only edit "local" files
	#  Read in the entire file and write out to a new file stanza-by-stanza
	#  1.  Write out everting to first stanza
	#  2.  Look at all data in the current stanza
	#  3.  find the sourcetype (if any)
	#  4.  Find the index (if any)
	#  5.  Look in the index map
	#  6.  WRite out the new stanza
	#  7.  Rinse and repeat
	#  
	#  Return a list of new files (if any)

	#  Get list of all inputs.conf in inputs_repo
	repo_path = cwd+"/inputs_repo/*inputs.conf"
	input_files = glob.glob(repo_path)

	new_files=[]

	for input_file_name in input_files:
		print ""
		print "Processing file "+input_file_name
		print "================"
		if "local" in input_file_name:
			print "This is a local file"
	
			with open(input_file_name,'r') as content_file:
				inputs_contents = content_file.read()
			inputs_list = inputs_contents.split("\n")
			#print "Read in the file "+input_file_name

			file_size = len(inputs_list)
			#print "File size is "+str(file_size)

			file_index = 0
			modified=0
			new_inputs_list = []
			first_stanza = 0
			bad=0

			#  Read the entire inputs_list and build a new_inputs_list
			while 1==1:

				input_line = inputs_list[file_index]
				#print ""
				#print input_line
				found_stanza = 0

				if ("[" in input_line) and ("]" in input_line):
					#  Found a stanza. Look for a sourcetype or index KV pair
					stanza_buffer = []
					found_sourcetype = 0
					found_stanza = 1 
					found_index=0
					stanza_position = 0
					index_name = ""
					stanza_buffer.append(input_line)
					#print "input_line="+str(input_line)+" stanza_buffer="+str(stanza_buffer)
					file_index=file_index+1
					input_line = inputs_list[file_index]
					while not (("[" in input_line) and ("]" in input_line)):
						if "index" in input_line:
							#  Found an index KV pair in the stanza.  Parse it.
							input_line_split = input_line.split("=")
							index_name = "".join(input_line_split[1].split())
							#print "Found index name "+index_name
							index_index = stanza_position
							found_index=1
						elif "sourcetype" in input_line:
							#  FOund a sourcetype KV pair in teh stanza, Parse it.
							input_line_split = input_line.split("=")
							sourcetype_name = "".join(input_line_split[1].split())
							#print "Found sourcetype named "+sourcetype_name
							found_sourcetype = 1 
						stanza_buffer.append(input_line)
						stanza_position = stanza_position+1
						file_index=file_index+1
						if file_index+1 >= file_size: 
							break
						input_line = inputs_list[file_index]
					#  At this point, the entire stanza as been copied and parsed.
					#  Check to see if the recorded stanza had a sourcetype
					if (found_sourcetype == 1):		
						#  Check to see if we need to change the index or inject a new index KV pair
						if index_name == "":
							#  The stanza did not have a declared index.
							#  Declare one and append to the stanza_buffer
							try:
								new_index = index_map[sourcetype_name]
								if new_index == "":
									print "ERROR. Found "+sourcetype_name+" in the csv sourcetype <-> index map, buthe NEW_INDEX value was missing."
							except:
								print "ERROR.  The sourcetype was found in "+input_file_name
								print "ERROR.    .... but an assigned index for "+sourcetype_name+" was not found in the spreadsheet csv file."
								bad=1
								#return(bad)
							index_kv = "index = "+new_index
							stanza_buffer.append(index_kv)
							modified=1
						else:
							#  The stanza did have a declared index.
							#  Check to see if it is correct and modifiy if needed
							try:
                                                                new_index = index_map[sourcetype_name]
								if new_index == "":
									print "ERROR. Found "+sourcetype_name+" in the csv sourcetype <-> index map, buthe NEW_INDEX balue was missing."
                                                        except: 
                                                                print "ERROR.  The sourcetype was found in "+input_file_name
                                                                print "ERROR.    .... but an assigned index for "+sourcetype_name+" was not found in the spreadsheet csv file."
								bad=1
                                                                #return(bad)
							if index_name == new_index:
								#  The sourcetype has the correct index.
								pass
							else:
								#  The sourcetype has the wrong index. Replace the line with teh correct index
								index_kv = "index = "+new_index
								stanza_buffer[index_index+1]=index_kv
								modified=1

						#  Copy the over the stanza
						for item in stanza_buffer:
							new_inputs_list.append(item)
					elif (found_sourcetype == 0) and (found_index==1):
						#  The stanza had an index KV pair by not a sourcetype
						print "WARN.  A monitor in "+input_file_name+" had an index "+index_name+" but no soucetype."
						for item in stanza_buffer:
							new_inputs_list.append(item)
					else:
						#  Found a stanza but did not see a sourcetype in the stanza. So just copy over. No edits.
						for item in stanza_buffer:
							new_inputs_list.append(item)

				else:
					#  This is a line outside of a stanza
					new_inputs_list.append(input_line)
					file_index=file_index+1

				#  Exit out of loop if we have reached the end of the file
				#print "file_index+1="+str(file_index+1)+" file_size="+str(file_size)
				if file_index+1 >= file_size:
					break
			
			#  Outside of the while loop
			#  Finished reading and parsing the file
			if (modified == 1) and (bad==0):
				#  Dump the contents into a new file
				new_file_name = input_file_name+".new"
				new_file = open(new_file_name,"w")
				for item in new_inputs_list:
					item_scrub = item.replace("\n","")
					new_file.write(item+"\n")
				new_file.close()
				new_files.append(new_file_name)
				print "A new file was created =>"+new_file_name
			else:
				print "No changes to the file "+input_file_name
					

		else:
			print "This is not a local file.  Moving on ...."
		print "Advancing to the next inputs.conf file ..."

	print "Finished processing all the inputs.conf files."

	return(new_files)


def get_credentials():


	#print str(tools.argparser)
	#print str(argparse.ArgumentParser(parents=[tools.argparser]))
	#print str(argparse.ArgumentParser(parents=[tools.argparser]).parse_args())

        flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
	print str(flags)

	client_secret_file = cwd+"/"+credential_name
        if not os.path.exists(client_secret_file):
                print "ERROR.  The Google Sheet secret file "+client_secret_file+" does not exist. Not ablwe to get sourcetype <-> index mapping"
                exit()
        print "client_secret_file="+client_secret_file

    	home_dir = os.path.expanduser('~')
    	credential_dir = os.path.join(home_dir, '.credentials')
    	if not os.path.exists(credential_dir):
        	os.makedirs(credential_dir)
    	credential_path = os.path.join(credential_dir, 'sheets.googleapis.com-break-main.json')

    	store = Storage(credential_path)
    	credentials = store.get()
    	if not credentials or credentials.invalid:
		print "Create credential file"
        	flow = client.flow_from_clientsecrets(client_secret_file, SCOPES)
        	flow.user_agent = APPLICATION_NAME
            	#credentials = tools.run_flow(flow, store, flags)
		credentials = tools.run_flow(flow, store)
        	print('Storing credentials to ' + credential_path)
    	return credentials

	
#
#   python ./read_google_sheet.py --noauth_local_webserver
#
def read_index_map(cwd):

	#  python ./read_google_sheet.py --noauth_local_webserver
	read_google_sheet_location = cwd+"/read_google_sheet.py"
        command = ['python',read_google_sheet_location,'--noauth_local_webserver']
        #print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        #print "stdout="+str(stdout)	
	row_split = stdout.split("\n")
	try:
		sourcetype_dict = {}
		sourcetype_list = []
		sourcetype_kv_pair = row_split[0]
		sourcetype_kv_split = sourcetype_kv_pair.split("=")
		sourcetype_kv_values = sourcetype_kv_split[1]
		sourcetype_cell_list = sourcetype_kv_values.split(",")
		first = 1
		for sourcetype_cell in sourcetype_cell_list:
			#print "Here0"
			sourcetype_cell_clean1 = sourcetype_cell.replace("[u'","")
			sourcetype_cell_clean2 = sourcetype_cell_clean1.replace("']","")
			sourcetype_cell_clean3 = sourcetype_cell_clean2.replace("[","")
			#print "Here 0.5"
			sourcetype_cell_clean4 = sourcetype_cell_clean3.replace(" ","")
			sourcetype_cell_clean5 = sourcetype_cell_clean4.replace("]","")
			#print "Here1"
			if first == 1:
				first=0
				#print "Here2"
				if sourcetype_cell_clean5 != "SOURCETYPE":
					print "ERROR.  Can not parse the sourcetype row returned by "+str(command)
					print "        "+str(sourcetype_cell_clean5)
					print"         Was expecting first cell value to be SOURCETYPE"
					print str(sourcetype_kv_pair)
					exit()
				continue
			#print "sourcetype cell = "+sourcetype_cell_clean5
			sourcetype_dict[sourcetype_cell_clean5]=""
			#print "Here3"
			sourcetype_list.append(sourcetype_cell_clean5)
	except:
		print "ERROR.  Can not parse the sourcetype row returned by "+str(command)
		print str(sourcetype_kv_pair)
		exit()

        try:
                index_kv_pair = row_split[1]
                index_kv_split = index_kv_pair.split("=")
                index_kv_values = index_kv_split[1]
                index_cell_list = index_kv_values.split(",")
		first = 1
		index=0
                for index_cell in index_cell_list:
                        index_cell_clean1 = index_cell.replace("[u'","")
                        index_cell_clean2 = index_cell_clean1.replace("']","")
                        index_cell_clean3 = index_cell_clean2.replace("[","")
			index_cell_clean4 = index_cell_clean3.replace("]","")
			index_cell_clean5 = index_cell_clean4.replace(" ","")
			if first == 1:
				first=0
				if index_cell_clean5 != "NEW_INDEX":
					print "ERROR.  Can not parse the new new index returned by "+str(command)
					print"         Was expecting first cell value to be NEW_INDEX"
					print str(index_kv_pair)
					exit()
				continue
			sourcetype_name = sourcetype_list[index]
			#print "index cell = "+index_cell_clean5+" index="+str(index)+" sourcetype_name="+sourcetype_name
                        sourcetype_dict[sourcetype_name]=index_cell_clean5
			index=index+1
	except:
		print "ERROR.  Can not parse the new_index returned by "+str(command)
		#print str(index_kv_pair)
		exit()

	return(sourcetype_dict)		


def scp_new_input_files(cwd,target_hostname,splunk_home,whoiam,new_files):

	#  Upload each new file into the /tmp directory
	#  chown each file
	#  move the file into the respective directory but KEEP the .new extention
	#  A separate script will backup old inputs.conf and replace with the inputs.conf.new

	print "Important ... newly created inputs.conf.new files are being deposited onto "+target_hostname
	print "              These .new files do not take effect until they replace the inputs.conf files and Splunk is restarted\n"
	for new_file in new_files:
                command = ['scp',new_file,target_hostname+':/tmp/inputs_repo/']
		#print str(command)
                output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                stdout, stderr = output.communicate()
		#print "stdout="+str(stdout)

		command = ['ssh',target_hostname,'sudo chown splunk:splunk /tmp/inputs_repo/*.new']
		#print str(command)
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		#print "stdout="+str(stdout)

		new_file_split = new_file.split("/")
		new_file_name = new_file_split[-1]
		new_file_path = new_file_name.replace("_","/")
		command = ['ssh',target_hostname,'sudo -u splunk cp /tmp/inputs_repo/'+new_file_name+' '+new_file_path]
		#print str(command)
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		#print "stdout="+str(stdout)

		print "Deposited "+new_file_path

	return()
		

if __name__ == "__main__":

#    Given a specific host, this script will :
#       1.  read the index.map file and create an internal mapping between sourcetype and index
#       2.  Find all the inputs.conf file in the working Splunk instance
#       3.  scp all the inputs.conf files locally
#       4.  process all the inputs.conf files and change/insert the index=_____
#       5.  scp each inputs.conf back into its original directory.
	
	# Parse arguments   
	parse = argparse.ArgumentParser(usage='%(prog)s hostname copy_new_files_to_host(T/F)', description='Change the "index=" KV pair for every sourcetype on the specified host according to the spreadsheet in Google Doc.')
	parse.add_argument('hostname', nargs=1, help='The name of the host that has the Splunk FWDer configs. e.g. myhost.snc1')
	#parse.add_argument('index_map',nargs=1, help='The name of the csv file that has the sourcetype-to-indexName mappsing')
	parse.add_argument('copy_new_files_to_host',nargs=1, help='T or F to copy any newly created inputs.conf files up to the target host.')
	args = parse.parse_args()

	target_hostname = args.hostname[0]
        #index_map = args.index_map[0]
        copy_new_files_to_host = args.copy_new_files_to_host[0]
	
	#target_hostname = "orders-app3.snc1"
	#index_map = "ff"
	#copy_new_files_to_host = "F"

	#  Create a lock file to prevent more than one process working on the same host at the same time
	cwd = os.getcwd()
	lockFile = set_lock(target_hostname,cwd)

	#  Read in and build the index_lut
	index_lut = read_index_map(cwd)
	print "\nFound "+str(len(index_lut))+" sourcetype in the sourcetype Google Sheet.\n"

	if len(index_lut) != 0:
		# Get to the target host and find Splunk Home. Home is were "/bin/splunk status" is running.  
		splunk_home = get_splunk_home(cwd,target_hostname)
		if splunk_home != "":
			if (debug): print "Splunk Home is "+splunk_home

			command = ['whoami']
			output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			stdout, stderr = output.communicate()
			whoiam = "".join(stdout.split())
			print "Welcome "+whoiam

			#  Find all the "inputs.conf" files in the Splunk working directory
			#  cp the inputs.conf tile to "/tmp/etc-system-local-inputs.conf and chown to the users name
			#  scp all the files down to the local machine
			#result = scp_input_files(cwd,target_hostname,splunk_home,whoiam)

			# process all the inputs.conf files and change/insert the index=_____
			new_files = process_local_input_files(cwd,target_hostname,splunk_home,whoiam,index_lut)

			if len(new_files) > 0:
				# scp all the new files back up to the host and into their respective directories.
				#    Save save the original inputs.conf in the directory with inputs.conf-YYYY-MM-DD-HH-MM-SS
				if copy_new_files_to_host == "T":
					print "\n\nGonna upload "+str(new_files)
					scp_new_input_files(cwd,target_hostname,splunk_home,whoiam,new_files)
					print "\nDone"
				else:
					print "\n\nNew inputs.conf files have been been created. But you have elected to NOT upload them to the target host."
			else:
				print "There are no inputs.conf files in local directories on host "+target_hostname+" that need to be updated."
	else:
		print "Can not proceed without a sourcetype <-> index map. Bye."
	
	remove_lock(lockFile)

	exit(0)


