################################################
#
#    This is a python wrapper around Ansible.
#	The exact order of operation can be found under the "main" method below.
#	The general flow is ...
#		A.  Get the host name from the command line 
#		B.  Gather all the host.yml and hostclass.yml configuration information
#		C.  Check to see if the host exists in splunk_ops_config.  If not, then create a host.yml with default configs.  Push up to production repo.  
#		D.  Create the playbook
#		E.  Run Ansible against the given host
#
#    Local Git Repo Management:
#	1.  The local git clone repo is assumed to be golden (as compared to the production git repo)
#	    A lock bit will keep this script from reading from or writting to the git clone if it is being updated by another process.
#	    Likewise, this script will set a lock bit before writing and pushing data to the production git repo
#
#    Who should run this script?
#	a.  Roller. As directed by the splunk pkg in hostclass
#       b.  The user or admin using the Splunk UI
#       c.  The rpm package the Zeus runs on boot
#       d.  A cron job that cycles through the list of known hosts every 24 hours.
#
###############################################

# TODO .... Add error handling in case the splunk ops config host.yml file doe snot have the required/expected key pair
# TODO ..... Protect against line 660 subprocess error with a "try"



#  Lock bit location relative to location of this script.
lockBitLocation = "lockDirectory"
logFileLocation = "logs"
urlConfigHost = "http://config/host"
urlConfigHostclass = "http://config/hostclass"
#urlSplunkConfigHost = "https://raw.github.com/splunk/splunk_ansible/master/splunk_ops_config"
urlSplunkConfigHost = "https://raw.github.com/splunk/splunk_ops_config/master"


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
from threading import Timer

#######
#
#  Setting the lock bit prevents the system from running two simulatanous process to update the same
#  host at the same time
#  Note:  This does not prevent against multiple Ansisble servers from accessing the same host. In which
#         case a lock bit must be set by the Ansible playbook on the taregt host.
#
#######
def set_lock(logFile,target_hostname, cwd):
	
	lockFileName = target_hostname+".lck"
	lockDir = cwd+"/"+lockBitLocation
	lockFileFullPath = lockDir+"/"+lockFileName
	if not os.path.isdir(lockDir):
		os.makedirs(lockDir)
		if (debug): print "Created lock directory "+lockDir

	#  Prevent the host from getting updated while the local splunk_apps repo is being updated.
	#  Look for ANY token with the updating_apps*.lck
	num_tries = 0
	while (num_tries < 5):
		num_tries = num_tries+1
		app_lock_list = glob.glob(lockDir+"/updating_apps_*.lck")
		if len(app_lock_list) > 0:
			log_message(logFile,"INFO. The splunk_apps repo is being updated. Wait 5 seconds and try again.")
			if (debug): print "INFO. The splunk_apps repo is being updated. Wait 5 seconds and try again."
			time.sleep(5)
		else:
			break
	if num_tries == 5:
		log_message(logFile,"ERROR. Can not proceed because the splunk_apps repo is locked.")
		if (debug): print "ERROR. Can not proceed because the splunk_apps repo is locked."
		stop_logging(logFile)
		exit()

	if os.path.isfile(lockFileFullPath):
		log_message(logFile,"ERROR. Lock file exists. Host is already being updated.")
		if (debug): print "ERROR. Lock file exists. Host is already being updated."
		stop_logging(logFile)
		exit(0)
	else:
		with open(lockFileFullPath, "w") as f:
    			f.write("")
			f.close()
			log_message(logFile,"The host lock bit has been set. Proceed ....")

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
	
#######
#
#  It should be assumed that multiple processes exist, all updating various hosts at the same time.
#  Therefore, logging to a single unified log is not supported. 
#  So per-host-logfiles are created. Each log file is unique for a given host at a given time.
#  Log files are in a Splunk friendly format so that teh data can be easily ingested into Splunk.
#
######
def start_logging(cwd,target_hostname,update_user_configs,target_hostclass):

	#  Get the current time and create the log file
	timestamp = time.strftime("%Y%m%d%H%M%S")
	logFileName = target_hostname+"-"+timestamp

	logDir = cwd+"/"+logFileLocation
	logFileFullPath = logDir+"/"+logFileName

	if not os.path.isdir(logDir):
                os.makedirs(logDir)
                if(debug): print "Created log directory "+logDir
        if os.path.isfile(logFileFullPath):
                if(debug): print "ERROR. Log file exists. "+logFileFullPath
                exit(0)
        else:   
		try:
                	f = open(logFileFullPath, "w")
		except:
			if (debug): print "ERROR.  Not able to open log file "+logFileFullPath
			exit(0)

	#  Populate the logfile with an opening event ..
	timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
	print logFileName
	f.write(timestamp+" target_hostname="+target_hostname+" update_user_configs="+update_user_configs+" target_hostclass="+target_hostclass+"\n")

	return(f)


def log_message(logFile,message):

	timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
	logFile.write(timestamp+" message='"+message+"'\n")
	return()	


########
#
#   Given the host name and optionally the serverclass name, this method parses relevant data form the ops_config host file
#   and associated hostclass file.
#
#######
def  parse_ops_config(logFile,target_hostname,target_hostclass):

	# Browse to the http://config/host/hostname
	# Setup the header so that data is returned in a yaml format
	url = urlConfigHost+"/"+target_hostname

	log_message(logFile,"Attempting to get ops-config host data from "+url)

    	try:
		req=urllib2.Request(url)
		req.add_header('accept', 'application/x-yaml')
		r = urllib2.urlopen(req)
		ops_config_host_data = yaml.load(r.read())
		#if(debug): print str(ops_config_host_data)
		log_message(logFile,"Successfully read host yaml file from ops_config")
    	except urllib2.HTTPError, e:
		log_message(logFile,"ERROR. HTTP Error: "+str(e.code))
		if(debug): print "HTTP error"
		if(debug): print e.code
		stop_logging(logFile)
		exit(1)
	except urllib2.URLError, e:
		log_message(logFile,"ERROR. URL Error: "+str(e.code))
		if(debug): print "URL error"
		if(debug): print e.args
		stop_logging(logFile)
		exit(2)

	# Obtain the serverclass name
	# Figure out the name of the url to query
	# Downlaod the serverclass data from http://config/hostclass/serverclass
	# Parse the yaml

	if target_hostclass=="":
		log_message(logFile,"serverclass name not provided. Must parse from host.yml data")
		hostclass=ops_config_host_data['hostclass']
	else:
		log_message(logFile,"serverclass name provided. ")
		hostclass=target_hostclass
	log_message(logFile,"hostclass="+hostclass)
	url = urlConfigHostclass+"/"+hostclass
	log_message(logFile,"Attempting to get ops-config hostclass data from "+url)

	try:
                req=urllib2.Request(url)
                req.add_header('accept', 'application/x-yaml')
                r = urllib2.urlopen(req)
		#if(debug): print str(r.read())
                ops_config_hostclass_data = yaml.load(r.read())
		#if(debug): print str(ops_config_hostclass_data)
                log_message(logFile,"Successfully read host hostclass file from ops_config")
        except urllib2.HTTPError, e:
                log_message(logFile,"ERROR. HTTP Error: "+str(e.code))
                if(debug): print "HTTP error"
                if(debug): print e.code
                stop_logging(logFile)
                exit(3)
        except urllib2.URLError, e:
                log_message(logFile,"ERROR. URL Error: "+str(e.code))
                if(debug): print "URL error"
                if(debug): print e.args
                stop_logging(logFile)
                exit(4)

	return(ops_config_host_data,ops_config_hostclass_data)


	

def stop_logging(fileHandle):

        #  Populate the logfile with an closing event ..
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        fileHandle.write(timestamp+" message=Stopped Logging.\n")
	fileHandle.close()

        return()

######
#
#  This method retreives all the splunk_ops_config data for the specified host
#
######
def parse_splunk_ops_config(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_pkg_name):

        # Browse to the https://raw.github.com/splunk/splunk_ops_config/
        # Setup the header so that data is returned in a yaml format
        url = urlSplunkConfigHost+"/"+target_hostname+".yml"

	print url
        log_message(logFile,"Attempting to get splunk_ops-config host data from "+url)

        try:
                req=urllib2.Request(url)
                req.add_header('accept', 'application/x-yaml')
                r = urllib2.urlopen(req)
                splunk_ops_config_host_data = yaml.load(r.read())
		#print str(splunk_ops_config_host_data)
                log_message(logFile,"Successfully read host yaml file from splunk_ops_config")
		return(splunk_ops_config_host_data)
        except urllib2.HTTPError, e:
                log_message(logFile,"HTTP return code: "+str(e.code))
		log_message(logFile,"This host does not exist in splunk_ops_config folder. It will be created with a set of default configs.")
                if(debug): print "Gotta make a host file for splunk_ops_config"
        except urllib2.URLError, e:
                log_message(logFile,"ERROR. URL Error: "+str(e.code))
                if(debug): print "URL error"
                if(debug): print e.args
                stop_logging(logFile)
                exit(6)

	#  Create the host.yml and push into splunk_ops_config
	try:
		newly_created_hostname = create_host_yml(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_pkg_name)
	except:
		colo = ops_config_host_data['colo']
		new_host_yml_name = ops_config_host_data['hostname']+"."+colo+".yml"
		newly_created_hostname = cwd+"/splunk_ops_config/"+new_host_yml_name
		print newly_created_hostname

	# Instead, read the local repo for the new host.yml configs
	r = open(newly_created_hostname,'r')
	splunk_ops_config_host_data = yaml.load(r.read())
	log_message(logFile,"Successfully read newly created host yaml file from local repo")
	#print str(splunk_ops_config_host_data)
	return(splunk_ops_config_host_data)


#######
#
#  This method creates a host.yml file to be pushed into the splunk_ops_config folder.
#  The contents of the hosts.yml file are taken from the ops_config files and applied to the default/template .yml in splunk_ops_config
#
######
def create_host_yml(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_pkg_name):

	log_message(logFile,"Creating host.yml for splunk_ops_config based on package: "+splunk_pkg_name)

	# Bring down the requisite template based on the package called out for in the hostclass.yml file
	# The selected template type is either "splunk" or "splunkforwarder"
	#                       needs colo
	#                       needs env: production, or staging, or uat
	#  default_<type>_<env>.colo.yml
	if "splunkforwarder" in splunk_pkg_name: type="splunkforwarder"
	else: type="splunk"
	colo = ops_config_host_data['colo']
	env = ops_config_host_data['ops_params']['environment']
	template_name = "default_"+type+"_"+env+"."+colo+".yml"

	url = urlSplunkConfigHost+"/"+template_name
	if(debug): print url
	log_message(logFile,"Using the following template to create the host.yml file in splunk ops config folder: "+template_name)

	try:
                req=urllib2.Request(url)
                req.add_header('accept', 'application/x-yaml')
		r = urllib2.urlopen(req)
                new_host = yaml.load(r.read())
                log_message(logFile,"Successfully read host yaml file from splunk_ops_config")

        except urllib2.HTTPError, e:
		log_message(logFile,"ERROR. HTTP Error: "+str(e.code))
		if(debug): print "HTTP error"
		if(debug): print e.args
		exit(7)
        except urllib2.URLError, e:
                log_message(logFile,"ERROR. URL Error: "+str(e.code))
                if(debug): print "URL error"
                if(debug): print e.args
                stop_logging(logFile)
                exit(8)

	#  Populate the template file
	new_host['hostname']=ops_config_host_data['hostname']
	new_host['hostclass']=ops_config_host_data['hostclass']
	new_host['id']=ops_config_host_data['id']
	new_host['creation_timestamp']=time.strftime("%Y-%m-%d %H:%M:%S")
	new_host['update_window_start_date']=time.strftime("%Y-%m-%d")
	new_host['update_window_stop_time']=str(new_host['update_window_stop_time'])

	# Make sure that time is in the HH:MM:SS format
	if ":" not in str(new_host['update_window_stop_time']):
		time_str = time.strftime("%H:%M:%S",time.gmtime(int(new_host['update_window_stop_time'])))
		#print str(time_str)
		new_host['update_window_stop_time']=str(time_str)

        # Pick the latest "template_generic_v" from the splunk ops_config playbook repo
	template_list = glob.glob(cwd+"/splunk_playbooks/template_generic_v*")
	latest_version=0
	try:
		for playbook in template_list:
			version = playbook.split("template_generic_v")[1]
			if int(version) > latest_version: latest_version=int(version)
		target_playbook = "template_generic_v"+str(latest_version)
	except:
		log_message(logFile,"Error.  Could not find latest template_generic_v from "+str(template_list))	
		if(debug): print "Exception:"+str(template_list)
		target_playbook = "template_generic_v1"
	new_host['playbook_template'] = target_playbook

	# Create a file and push that file up to splunk/splunk_ansible
	new_host_yml_name = ops_config_host_data['hostname']+"."+colo+".yml"
	new_host_yml_name_full_path = cwd+"/splunk_ops_config/"+new_host_yml_name

	# Note:  No need to check the lock bit. There can only be ONE process working on a specific host at any given time.
	#        Any repo update would not wipe out the host.yml about to be created. 
	log_message(logFile,"Creating a new host.yml file called: "+new_host_yml_name)
	#print new_host_yml_name
	try:
        	f = open(new_host_yml_name_full_path, "w")
		f.write(yaml.dump(new_host))
		f.close()
		log_message(logFile,"Created a new host.yml file")
		if (debug): print "Created "+new_host_yml_name
        except:
		if (debug): print "ERROR.  Not able to create new host yml file "+new_host_yml_name
		log_message(logFile,"Creating a new host.yml file called: "+new_host_yml_name)
		exit(0)

	#  Push the new host yml file to splunk ops config
	#  Only able to push AFTER this process detects no lock bit and then sets it for itself.
	#command = 'cd '+cwd+'/splunk_ops_config; sudo -u svc_configator git add .; sudo -u svc_configator git commit -m "Adding a host '+new_host_yml_name+' to the splunk_ops_config folder"; sudo -u svc_configator git push' 
	command = 'cd '+cwd+'/splunk_ops_config; add .; commit -m "Adding a host '+new_host_yml_name+' to the splunk_ops_config folder"; git push'
	#print command
	lock_name = check_set_repo_lock(cwd)
	log_message(logFile, command)
	#log_message(logFile,"Pushed the new host yml file to splunk ops config")

	output=subprocess.check_output(command, shell=True)
	log_message(logFile,"Pushed the new host yml file to splunk ops config")
	log_message(logFile, str(output))

	# Check output to look for success text 
	# 1 file changed
	if "1 file changed" in output:
		log_message(logFile,"Successfully pushed "+new_host_yml_name+" to git hub production repo")
		try:
			os.remove(lock_name)
			if (debug): print "Commit pushed new host.yml file. git hub lck removed."
			log_message(logFile,"Successfully removed lock file "+lock_name)
		except:
			log_message(logFile,"Removed lock file "+lock_name)
	else:
		log_message(logFile,"It appears that the push to production git did not succeed."+str(output))
		if (debug): print str(output)

	return(cwd+"/splunk_ops_config/"+new_host_yml_name)


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
			log_message(logFile,"Sleep. Waiting for git_repo.lck bit to be cleared.")       
               		if (debug): print "Waiting for git_repo.lck bit to be cleared."
			i=i+1
		if i==100:
			log_message(logFile,"Sleep. Waiting for git_repo.lck bit to be cleared.")
			if (debug): print "git_repo.lck bit never cleared."
			exit(0)

		log_message(logFile,"git_repo.lck bit is cleared.")
       		with open(lockFileFullPath, "w") as f:
			f.write("")
			f.close()

		# Check to make sure that we got the lock
		if os.path.isfile(lockFileFullPath):
			log_message(logFile,"Created repo lock file "+lockFileFullPath)
			if (debug): print("Created repo lock file "+lockFileFullPath)
			return(lockFileFullPath)
		else:
			log_message(logFile,"Someone else grabbed the lock file "+lockFileFullPath)
			log_message(logFile,"Try again.")
			j=j+1


	log_message(logFile,"Giving up. Not able to create lock file.")
	if (debug): print "Giving up. Not able to create lock file."
	exit(0)

#######
#
#   Check to see that this host (as specified in ops_config) is supposed to be Ansible managed.
#   Splunk hosts that are supposed to be managed by Ansible will NOT have the usual Splunk package  e.g. 'splunk-5.0.5', or 'splunk_forwarder-2015.01.14_01.09'
#   Rather they will have a package that conforms to (?P<type>[^-]+)_managed-(?P<version>[^-]+)-(?P<release>[^.]+).(?P<arch>.*).  e.g.  splunkforwarder_managed-6.2.3-264376.x86_64
#
#   Note;  Only one Splunk package needs to be instantiated in the ops_config file.
#   Note:  The version number and realease number are needed for yum install.
#
#######
def splunk_ansible_pkg_exist(logFile,ops_config_hostclass_data):

	log_message(logFile,"Check to see if this host is supposed to be managed by Ansible.")

	#  splunkforwarder_management-2017.04.11_16.14
        regex = r"splunk.*_management-(?P<version>.+)"
        try:
                for item in ops_config_hostclass_data['packages']['production']:
                        matches = re.findall(regex,item)
                        if matches:
				#print "item="+item
				log_message(logFile,"Ansible package found in ops-config: "+item)
				return(item)
        except:
		log_message(logFile,"This is not an Ansible managed host. Abort!")
		return("")

	log_message(logFile,"This is not an Ansible managed host. Abort!")
	return("")


######
#
#  Check that the host.yml config in the ops_config repo bear some basic resemblance to the configs in the splunk_ops_config
#  Specifically:  hostname, id, hostclass, colo
#
#####
def sanity_check_configs(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_ops_config_host_data):

	configs_match = True
	if ops_config_host_data['hostname'] != splunk_ops_config_host_data['hostname']: 
		configs_match = False
		print "The hostname does not match. "+ops_config_host_data['hostname']+" "+splunk_ops_config_host_data['hostname']
		log_message(logFile,"The hostname does not match")
	if ops_config_host_data['id'] != splunk_ops_config_host_data['id']: 
		configs_match = False
		print "The id does not match. "+ops_config_host_data['id']+" "+splunk_ops_config_host_data['id']
		log_message(logFile,"The id does not match.")
	if ops_config_host_data['colo'] != splunk_ops_config_host_data['colo']: 
		configs_match = False
		print "The colo not match. "+ops_config_host_data['colo']+" "+splunk_ops_config_host_data['colo']
		log_message(logFile,"The colo does not match.")

	if not configs_match:
		log_message(logFile,"The host configs beween ops_config and splunk_ops_config do not match!")
		log_message(logFile,str(ops_config_host_data))
		log_message(logFile,str(splunk_ops_config_host_data))
		if (debug): print "The host configs beween ops_config and splunk_ops_config do not match!"
		return(configs_match)
	else:
		log_message(logFile,"The host configs beween ops_config and splunk_ops_config match!")
		if (debug): print "The host configs beween ops_config and splunk_ops_config match!"

	return(configs_match)
	

######
#
#  Look at the admin controls on splunk_ops_config to see if an Ansible push is allowed to proceed on this host
#     based on the hostname and the time window
#
#####
def push_allowed(splunk_ops_config_host_data):

	allowed = False
	if splunk_ops_config_host_data['enable_ansible'] != True:
		return(allowed)

	#  NOTE:  All time is in UTC.
	#
	#  Allowed window if stop year is 9999:
	#      * Current timestamp >= start timestamp 
	#      * Current time < stop time
	#
	# Allowed window if stop year != 9999:
	#      * Current timestamp >= start timestamp
	#      * Current timestamp <  end timestamp
	#
	update_window_start_date = splunk_ops_config_host_data['update_window_start_date']
	update_window_start_time = splunk_ops_config_host_data['update_window_start_time']
	update_window_stop_date = splunk_ops_config_host_data['update_window_stop_date']
	update_window_stop_time = splunk_ops_config_host_data['update_window_stop_time']

	start_timestamp = str(update_window_start_date)+" "+str(update_window_start_time)
	stop_timestamp = str(update_window_stop_date)+" "+str(update_window_stop_time)

	start_timestamp_epoch=int(time.mktime(time.strptime(start_timestamp,"%Y-%m-%d %H:%M:%S")))
	stop_timestamp_epoch=int(time.mktime(time.strptime(stop_timestamp,"%Y-%m-%d %H:%M:%S")))
	start_time_secs=int(time.mktime(time.strptime(update_window_start_time,"%H:%M:%S")))
	stop_time_secs=int(time.mktime(time.strptime(update_window_stop_time,"%H:%M:%S")))

	current_timestamp_epoch=int(time.time())
	t = time.gmtime()
	current_secs_since_midnight = t.tm_sec + (t.tm_min*60) + (t.tm_hour * 3600)

	stop_year=str(update_window_stop_date)[0:3]

	#print "start_timestamp="+start_timestamp
	#print "stop_timestamp="+stop_timestamp

	if stop_year == "9999":
		if current_timestamp_epoch < start_timestamp_epoch: return(False)
		if current_secs_since_midnight > stop_time_secs: return(False)
	else:
		if current_timestamp_epoch < start_timestamp_epoch: return(False)
		if current_timestamp_epoch >= stop_timestamp_epoch: return(False)

	return(True) 


#######
#
#   Create the Ansible playbook.
#
#######
def create_playbook(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_ops_config_host_data,flag):

	# If a playbook already exists for this host, then compare the existing playbook with a newly constructed playbook
	# create the new playbook in a /construction_zone under host.colo
	# use templates to create the new playbook
	# compare the playbook. If no difference, then no need to push the new version of the playbook back into the repo
	# But, even if there is not diff, the playbook should be executed to update and change that might have occurred on the host

	target_playbook = splunk_ops_config_host_data['playbook_template']
	if (debug): print "Going to create a playbook based on "+target_playbook
	
	try:
		#  Make a copy of the template playbook in its entirety
		src = cwd+"/splunk_playbooks/"+target_playbook
		dst = cwd+"/construction_zone/"
        	if (debug): command = 'cp -fr '+src+' '+dst
        	print command
		output=subprocess.check_output(command, shell=True)
		# Rename the default playbook directlry name to the actual host name
		src = cwd+"/construction_zone/"+target_playbook
		dst = cwd+"/construction_zone/"+target_hostname
		command = 'mv '+src+' '+dst
		if (debug): print command
		output=subprocess.check_output(command, shell=True)
		#  Keep the template file around for a bit. The template file is needed to rebuild a new .yml file
		template_yml = cwd+"/construction_zone/"+target_hostname+"/hostName.colo.yml"
		target_yml = cwd+"/construction_zone/"+target_hostname+"/"+target_hostname+".yml"
		#command = 'cp '+src+' '+dst
                #if (debug): print command
                #output=subprocess.check_output(command, shell=True)
		#subprocess.call(['mv',src,dst],shell=False)
	except:
		log_message(logFile,"ERROR. Not able to "+command)
		if (debug): print "ERROR. Not able to "+command
		return(False)

	try:
		#  Read the newly host.yml playbook to change its vars
		playbook_file = open(template_yml,"r")
		host_var_config_data = yaml.load(playbook_file.read())
		playbook_file.close()
                log_message(logFile,"Successfully read host yaml file with var data.")
	except:
		log_message(logFile,"ERROR. Not able to read and parse "+template_yml)
                if (debug): print "ERROR. Not able to read "+template_yml
                return(False)

	#  Change the vars in the template based on the configs found in host.yml (roller) host.yml (admin configs)
	new_host_var_config_data = set_host_vars(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_ops_config_host_data,host_var_config_data)
	if bool(new_host_var_config_data):

		#  Can not rely on python's yaml.dump method to create Ansible formated yml files. Sigh!
		#print "new_host_var_config_data"
		#print str(new_host_var_config_data)
		dict_to_ansible_yaml(new_host_var_config_data,template_yml,target_yml)
		log_message(logFile,"Created new "+target_yml+" from "+template_yml)
		if (debug): print "Created new "+target_yml+" from "+template_yml
		subprocess.call(['rm','-rf',template_yml],shell=False)
		log_message(logFile,"Removed "+template_yml)
		if (debug): "Removed "+template_yml
		#with open(dst,"w") as playbook_file:
		#	yaml.dump(new_host_var_config_data,playbook_file,default_flow_style=False,canonical=True)

		#  Check to see if a playbook already exists in the repo
		if os.path.isdir(cwd+"/splunk_playbooks/"+target_hostname):
			#  If so .... compare the two playbooks.
			#command = ['diff','-rq',cwd+"/splunk_playbooks/"+target_hostname,cwd+"/construction_zone/"+target_hostname,'--exclude="*.retry"']
			command = 'diff -rf '+cwd+'/splunk_playbooks/'+target_hostname+' '+cwd+'/construction_zone/'+target_hostname+' --exclude="*.retry"'
			#command = 'diff -rf '+cwd+'/splunk_playbooks/'+target_hostname+' '+cwd+'/construction_zone/'+target_hostname
			log_message(logFile,str(command))
			if (debug): print str(command)
			#output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			output=subprocess.Popen(command,shell=True,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			#stdout=subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
			stdout, stderr = output.communicate()
			log_message(logFile,"Differences found in existing and new playbook =>"+str(stdout)+"<=")
			#print "stdout=>"+str(stdout)
			#print "stderr=>"+str(stderr)
			
			if len(str(stdout)) == 0:
				#  no difference, remove the playbook in construction
				log_message(logFile,"Newly constructed playbook from user/admin configs matches the playbook in the repo. No need to update the repo.")
				if (debug): print "no difference, remove the playbook in construction"
				shutil.rmtree(cwd+"/construction_zone/"+target_hostname,ignore_errors=True)
				if (debug): print "Deleted playbook in construction folder"
				push_playbook=False
			else:
				#  remove the repo playbook and replace with the new playbook, and push the new playbook up into the repo.
				#  Need to get a lock on the repo to make sure we are not in motion
        			lock_name = check_set_repo_lock(cwd)
				shutil.rmtree(cwd+"/splunk_playbooks/"+target_hostname,ignore_errors=True)
				if (debug): print "Removed playbook in repo"
				shutil.move(cwd+"/construction_zone/"+target_hostname,cwd+"/splunk_playbooks/"+target_hostname)
				if (debug): print "Moved newly constructed  playbook to repo"
				log_message(logFile,"Moved newly constructed  playbook to repo")
				push_playbook=True
		else:
			# No playbook in repo. So move over the newly contructed playbook
			push_playbook=True
			lock_name = check_set_repo_lock(cwd)
			shutil.move(cwd+"/construction_zone/"+target_hostname,cwd+"/splunk_playbooks/"+target_hostname)
			log_message(logFile,"Successfully put the newly constructed playbook into the repo directory")
			if (debug): print "Moved newly constructed  playbook to repo"

		if (push_playbook):
			if (flag == "L"):
				kill_proc = lambda p: p.kill()
				command = 'cd '+cwd+'/splunk_playbooks; sudo -u svc_configator git add .'
				log_message(logFile,command)
				output=subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
				log_message(logFile,str(output))
				print str(output)
				command = 'cd '+cwd+'/splunk_playbooks; sudo -u svc_configator git commit -m "Adding a newly constructed playbook '+target_hostname+'"'
				log_message(logFile,command)
				output=subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
				print str(output)
				log_message(logFile,str(output))
				log_message(logFile,"Going to rely on cron job to push playbooks.")
				#  Forego pushing the new playbook. Cuz there is a corn job that auto pushes every 10 mins.
				#try:
				#	command = 'cd '+cwd+'/splunk_playbooks; git push'
				#	log_message(logFile,command)
				#	output=subprocess.Popen(command,shell=True,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
					#output=subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
				#	timer = Timer(7, kill_proc, [output])
				#	timer.start()
				#	log_message(logFile,"Start timer")
				#	stdout, stderr = output.communicate()
				#	print str(stdout)
				#	log_message(logFile,str(stdout))
				#finally:
				#	log_message(logFile,"Timer canceled")
				#	timer.cancel()
				#	command = 'cd '+cwd+'/splunk_playbooks; sudo -u svc_configator git push'
				#	log_message(logFile,command)
				#	output=subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
				#	print str(output)
				#	log_message(logFile,str(output))
			else:
				command = 'cd '+cwd+'/splunk_playbooks; git add .; git commit -m "Adding a newly constructed playbook '+target_hostname+' to the splunk_ops_config/playbook folder"; git push'
				log_message(logFile,command)
        			output=subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
				log_message(logFile,str(output))
        		#if "1 file changed" in output:
                	#	log_message(logFile,"Successfully pushed "+target_hostname+" to git hub production repo")
			#	if (debug): print "Successfully pushed to git hub production repo"
                	#	try:
                        #		if (debug): print "Commit pushed new host.yml file. "
                        #		log_message(logFile,"Successfully pushed new playbook into repo.")
                	#	except:
                        #		log_message(logFile,"Not able to push new playbook into repo.")
        		#else:
                	#	log_message(logFile,"It appears that the push to production git did not succeed."+str(output))
                	#	if (debug): print str(output)
			#	#  Okay to proceed.

			os.remove(lock_name)

		return(True) 

	else:
		log_message(logFile,"ERROR. Abort building playbook. Could not parse user configs.")
		if (debug): print "ERROR. Not building playbook. Could not parse user configs."
		return(False)

	

def set_host_vars(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_ops_config_host_data,host_var_config_data):

	new_host_var_config_data = {}
	try:
		ops_config_host_data_params = ops_config_host_data['params']
		#print "ops_config_host_data_params=>"+str(ops_config_host_data_params)
		ops_config_host_data_params_splunk = ops_config_host_data_params['splunk']
		#print "ops_config_host_data_params_splunk=>"+str(ops_config_host_data_params_splunk)
	except:
		log_message(logFile,"ERROR. The Splunk params in ops-config are whacky. Not able to parse.")
		if (debug): print "ERROR. The Splunk params in ops-config are whacky. Not able to parse."

	# admin apps is optional. Possibel that there are none to apply
	if 'admin_apps' in splunk_ops_config_host_data: new_host_var_config_data['admin_apps'] = splunk_ops_config_host_data['admin_apps']
	# admin_system_configs should be there.
	if 'admin_system_configs' in splunk_ops_config_host_data: new_host_var_config_data['admin_system_configs'] =  splunk_ops_config_host_data['admin_system_configs']
	# install_user_name if missing should default to "splunk"
	if 'install_user_name' in ops_config_host_data_params_splunk: new_host_var_config_data['install_user_name'] =  ops_config_host_data_params_splunk['install_user_name']
	else: new_host_var_config_data['install_user_name'] = "splunk"
	# local_git_repo should exist. But if missing, default to /var/directory/manage_splunk/
	if 'local_git_repo' in splunk_ops_config_host_data: new_host_var_config_data['local_git_repo'] =  splunk_ops_config_host_data['local_git_repo']
	else: new_host_var_config_data['local_git_repo'] = "/var/directory/manage_splunk/"
	# number_of_splunk_instances_to_install defaults to 1
	if 'number_of_splunk_instances_to_install' in ops_config_host_data_params_splunk: new_host_var_config_data['number_of_splunk_instances_to_install'] = ops_config_host_data_params_splunk['number_of_splunk_instances_to_install']
	else: new_host_var_config_data['number_of_splunk_instances_to_install'] = '1'
	# rpm name MUST exist. No default
	new_host_var_config_data['rpm_name'] = ops_config_host_data_params_splunk['rpm_name']
	# splunk_install_target_directory default to /var/directory/
	if 'splunk_install_target_directory' in ops_config_host_data_params_splunk: new_host_var_config_data['splunk_install_target_directory'] = ops_config_host_data_params_splunk['splunk_install_target_directory']
	else: new_host_var_config_data['splunk_install_target_directory'] = "/var/directory/"
	# splunk_boot_start is optional. Defaults to True
	if 'splunk_boot_start' in ops_config_host_data_params_splunk: new_host_var_config_data['splunk_boot_start'] = ops_config_host_data_params_splunk['splunk_boot_start']
	else: new_host_var_config_data['splunk_boot_start'] = "True"
	# restart_on_config_change is an option. Default to true
	if 'restart_on_config_change' in splunk_ops_config_host_data: new_host_var_config_data['restart_on_config_change'] = splunk_ops_config_host_data['restart_on_config_change']
	else: new_host_var_config_data['restart_on_config_change'] = "true"
	# splunk_type probably should not be an option. Hwever, if it is missing ....
	if 'splunk_type' in ops_config_host_data_params_splunk: new_host_var_config_data['splunk_type'] = ops_config_host_data_params_splunk['splunk_type']
	new_host_var_config_data['splunk_type'] = "splunkforwarder"
	# I suppose there may not be any user apps
	if 'user_apps' in ops_config_host_data_params_splunk: new_host_var_config_data['user_apps'] = ops_config_host_data_params_splunk['user_apps']
	new_host_var_config_data['white_list_user_apps'] = splunk_ops_config_host_data['white_list_user_apps']
	try:
		rpm_name=new_host_var_config_data['rpm_name']
		#print "rpm_name="+str(rpm_name)
		rpm_name_split = rpm_name.split(".rpm")
		#print "split rpm_name=>"+str(rpm_name_split)
		new_host_var_config_data['yumdownloader_name'] = rpm_name_split[0]
		#print str(rpm_name_split[0])
		new_host_var_config_data['yumdownloader_name_noarch'] = rpm_name_split[0][:-7]
	except:
		log_message(logFile,"ERROR. Not able to parse rpm_name from ops-config host.yml file: "+rpm_name)
		if (debug): print "ERROR. Not able to parse rpm_name from ops-config host.yml file: "+rpm_name
		new_host_var_config_data={}
		return(new_host_var_config_data)

	return(new_host_var_config_data)


#######
#  
#   Python does not appear to have a module that write yaml in the Ansible acceptable syntax.
#   This method relaies on a template file and replaces values in the template file with 
#   the new values found in the given dictionary
#
#######
def dict_to_ansible_yaml(test_dict,template_filename,out_filename):

	#print "test_dict"
	#print str(test_dict)

	template_lines = []
	template_file = open(template_filename,"r")
	for item in template_file:
		template_lines.append(item)
	template_file.close()

	out_file = open(out_filename,"w")

	for template_line in template_lines:
		for item in test_dict:
			edit_line = False
			if str(item)+":" in template_line:
				edit_line = True
				break
		if not (edit_line):
			out_file.write(template_line)
		else:
			#print "template_line=>"+str(template_line)
			template_line_split=template_line.split(":")
			#print "template_line_split=>"+str(template_line_split)
			key_name = template_line_split[0].lstrip()
			key_value = test_dict[key_name]
			#print "kv=>"+str(key_name)+"="+str(key_value)
			new_item = template_line_split[0]+": "+str(key_value)+"\n"
			#print "new_item=>"+str(new_item)
			out_file.write(new_item)			

	out_file.close()

	return()

def splunk_restart(cwd,logFile,ops_config_host_data,splunk_ops_config_host_data,target_hostname,ansible_stdout):

	#  First check to see if Splunk Ops Config is allowing restarts on Change
	restart_allowed = splunk_ops_config_host_data['restart_on_config_change']
	#print "restart_allowed="+str(restart_allowed)

	# Look to see if any of the new app or configs changed on the Splunk host
	ansible_stdout_list = ansible_stdout.split("\n")
        detect=0
        changed_config = 0
        for item in ansible_stdout_list:
                print item
                if "RESTART" in item:
                        print "Found the begining of an RESTART block"
                        detect=1
                        continue
		if ("Remove user app" in item) or ("Remove system configs" in item):
			# Found the second where user pass are being removed.
			detect=1
			continue
                if (detect == 1):
                        if ":" not in item:
                                print "End of RESTART block. Not changed event found"
                                detect=0
                                continue
                        elif "changed:" in item:
                                print "Change event found"
                                changed_config = 1
                                break

	if changed_config == 1:
		if (debug): print "Detected a config change."
		log_message(logFile,"Detected a config change.")
	else:
		if (debug): print "No config change detected"
		log_message(logFile,"No config change detected")

	if (restart_allowed==True):
		if (debug): print "Allowed to restart if a config change was detected."
		log_message(logFile,"Allowed to restart if a config change was detected.")

		#  At this point we have parsed the entire Anisible exhaust looking for changed app on resync
		if changed_config == 1:

			#  Start or re-start splunk ?  Depends on Splunks current state.
			#     python ./detect_splunk_state.py splunk3-dev.snc1
			path_to_script = cwd+"/detect_splunk_state.py"
                        command = ['python',path_to_script,target_hostname]
                        log_message(logFile,str(command))
                        #if (debug): print str(command)
                        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        stdout, stderr = output.communicate()
			log_message(logFile,str(stdout))
			#if (debug): print stdout

			# Parse output to get current status of splunk instance
			stdout_list = stdout.split("\n")
			ops_config_host_data_params = ops_config_host_data['params']
			ops_config_host_data_params_splunk = ops_config_host_data_params['splunk']
			splunk_type = ops_config_host_data_params_splunk['splunk_type']
			if splunk_type == "splunk":
				response = stdout_list[1]
			else:
				response = stdout_list[0]

			#Expected reponses:  "not running", "running", "gobbdley gook" - meaning that splunk has not been started yet.
			path_to_script = cwd+"/change_splunk_state.py"
			if "not running" in response :
				log_message(logFile,"Host was not running and will need to be started")
				if (debug): print "Host was not running and was started"
				# python ./change_splunk_state.py hostname start
				command = ['python',path_to_script,target_hostname,"start",splunk_type]
			elif "running" in response:
				log_message(logFile,"Host was running and will need to be restarted")
				if (debug): print "Host was running and will need to be restarted"
				command = ['python',path_to_script,target_hostname,"restart",splunk_type]
			else:
				log_message(logFile,"Host was in an unknown state and will be started")
				if (debug): print "Host was in an unknown state and will be started"
				command = ['python',path_to_script,target_hostname,'start --accept-license --answer-yes --no-prompt',splunk_type]
			
			log_message(logFile,str(command))
			if (debug): print str(command)
			output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			stdout, stderr = output.communicate()
			log_message(logFile,str(stdout))
			if (debug): print stdout

		else:
			if (debug): print "No config change detected"
			log_message(logFile,"No config change detected")

	else:
		if (debug): print "Not allowed to restart Splunk according to restart_on_config_change on Splunk ops config"
		log_message(logFile,"Not allowed to restart Splunk according to restart_on_config_change on Splunk ops config")

	return()


#
#  Look through playbook output for issues.
#
def parse_playbook_exhaust(stdout):

	if "UNREACHABLE" in stdout:
		print "The target host could not be accessed by user svc_configator."
		print "  ---  Are you sure the that the user 'svc_configator' exists on the target host?"
		print stdout
		return()

	if "Error: Package: glibc" in stdout:
		print "*********************************"
		print " ERROR"
		print "   The yum is not able to install glibc"
		print "   On the target host machine, try ...."
		print "      rpm -e --justdb --nodeps libselinux"
		print "      yum install libselinux"
		print "      yum install libselinux-python"
		print "********************************"
		return()




#
#  Make sure that the hostname ans servername on the target host matches the hostname specified in splunk ops config
#  Restart Splunk if name changed and Splunk is already running.
#  
def ensure_hostname_is_correct(cwd,logFile,target_hostname,password,splunk_full_path):

	#python ./set_hostname.py splunk1-dev.snc1 /var/directory/splunkforwarder turnbuckle1019
        path_to_script = cwd+"/set_hostname.py"
        command = ['python',path_to_script,target_hostname,splunk_full_path,password]
        log_message(logFile,str(command))
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

        return()




#
#  Setting the password has been relegated to a separate script so tha passwords can be somewhat locked up in a private git repo.
#
def set_admin_password(cwd,logFile,target_hostname,splunk_full_path):

	path_to_script = cwd+"/set_admin_password.py"
	command = ['python',path_to_script,target_hostname,splunk_full_path]
	log_message(logFile,str(command))
	print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	log_message(logFile,str(stdout))
	if (debug): print str(stdout)
	if "Success" in str(stdout):
		log_message(logFile,"INFO:  The admin password was changed.")
		if (debug): print "INFO:  The admin password was changed."
	else:
		log_message(logFile,"INFO:  The admin password was not changed.")
		if (debug): print "INFO:  The admin password was not changed."

	stdout_list = stdout.split("\n")
	password_is_next = 0
	for item in stdout_list:
		#print "item="+item+" password_is_next="+str(password_is_next)
		if password_is_next == 1:
			password = item
			#print "password="+password
			break
		if item == "Success" or item == "Fail":
			password_is_next = 1

	return(password)



#  Make sure that the target host has a base yum capability
def  base_yum_on_target_host(cwd,logFile,target_hostname):

	#    Try sudo yum install python-simpljson.  This is a test to see if base yum capabilities are on the host.
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo yum install -y python-simplejson']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate() 
	if "Error" not in str(stdout): 
		log_message(logFile,"It appears that yum baseline exists on this host")
		log_message(logFile,str(stdout))
		#if (debug): print str(stdout)
		if (debug): print "It appears that yum baseline exists on this host"
		return(True)

	#  Get rid of broken repo (if any)
	if "Cannot find a valid baseurl" in stdout:
		command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo mv /etc/yum.repos.d/CentOS-Base.repo /etc/yum.repos.d/CentOS-Base.repo.orig']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		log_message(logFile,str(command))
		log_message(logFile,str(stdout))
		if (debug): print "Moved problematic repo"

	#  Get the os version
	log_message(logFile,"Not able to yum install python-simplejson. Ansible is not going to run.")
	if (debug): print "Not able to yum install python-simplejson. Ansible is not going to run."
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo rpm -q centos-release']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate() 
	#  centos-release-5-6.el5.centos.1
	try:
		log_message(logFile,"Centos release is "+stdout)
		if (debug): print "Centos release is "+stdout
		stdout1 = stdout.split(".")[0]
		major_version = stdout1.split("-")[2]
		minor_version = stdout1.split("-")[3]
	except:
		major_version = "5"

	if major_version == "5":
		#  Lower versions of Centos yum do not seem to exist
		minor_version = "11"

	#  Create a pointer to a repo that thas the needed python-simpljson package.
	#/etc/yum.repos.d/configator.repo
	#[configator]
	#name=CentOS-$releasever - Base
	#baseurl=http://vault.centos.org/5.11/os/x86_64/
	#gpgcheck=1
	#gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-5
	file_contents = '"[configator]\nname=CentOS-$releasever  configator_base\nbaseurl=http://vault.centos.org/'+major_version+'.'+minor_version+'/os/x86_64/\ngpgcheck=1\ngpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-'+major_version+'\n"'
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo printf '+file_contents+' > /tmp/configator.repo']
	if (debug): print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	if (debug): print str(stdout)
	if (debug): print str(stderr)
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo mv /tmp/configator.repo /etc/yum.repos.d/configator.repo']
	if (debug): print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
        if (debug): print str(stdout)
        if (debug): print str(stderr)

	#  Try sudo yum install python-simpljson again.
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo yum install -y python-simplejson']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	if "base is listed more than once" in str(stdout):
		if (debug): print "Still no yum success."
		log_message(logFile,"Looks like we have too many yum repos. Gonna try and get rid of CentOS-Base.repo")
	elif "Error" in str(stdout):
		log_message(logFile,str(command))
		log_message(logFile,"Created a configator.repo in /etc/yum.repos.d, but yum STILL can not find python-simpljson package which is needed by Ansible.")
		log_message(logFile,str(stdout))
		log_message(logFile,str(stderr))
		log_message(logFile,"Abort!")
		if (debug): print "Created a configator.repo in /etc/yum.repos.d, but yum STILL can not find python-simpljson package which is needed by Ansible."
		if (debug): print str(stdout)
		return(False)

	if "base is listed more than once" in str(stdout):
		if (debug): print "Move the CentOS-Base.repo to CentOS-Base.repo.orig and try again ..."
		command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo mv /etc/yum.repos.d/CentOS-Base.repo /etc/yum.repos.d/CentOS-Base.repo.orig']
		if (debug): print str(command)
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		log_message(logFile,"Third time is a charm.")
		if (debug): print "And one more for the gipper."
		command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo yum install -y python-simplejson']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		if "Error" in str(stdout):
			log_message(logFile,str(command))
			log_message(logFile,"Created a configator.repo in /etc/yum.repos.d, but yum STILL can not find python-simpljson package which is needed by Ansible.")
			log_message(logFile,str(stdout))
			log_message(logFile,str(stderr))
			log_message(logFile,"Abort!")
			if (debug): print "Created a configator.repo in /etc/yum.repos.d, but yum STILL can not find python-simpljson package which is needed by Ansible."
			if (debug): print str(stdout)
			return(False)
		else:
			if (debug): print "Whew. It worked."

	log_message(logFile,"Created a configator.repo in /etc/yum.repos.d")
	if (debug): print "Created a configator.repo in /etc/yum.repos.d"
	return(True)



if __name__ == "__main__":
	
	# Parse arguments   prog='splunk_ansible',
	parse = argparse.ArgumentParser(usage='%(prog)s hostname update_user_configs [options]', description='Run Ansible playbook on specified host to maintain Splunk configurations')
	#parse = argparse.ArgumentParser()
	parse.add_argument('hostname', nargs=1, help='The name of the host to apply Splunk configs. e.g. myhost.snc1')
	parse.add_argument('update_user_configs', nargs=1, choices=['T','F','D','L'], help='T=Run playbook and start, D=Run playbook, F=Do not run playbook.')
	parse.add_argument('--hostclass', nargs='?', help='Optionally give the hostserver name of the host')
	args = parse.parse_args()
	target_hostname = args.hostname[0]
	update_user_configs = args.update_user_configs[0]
	target_hostclass = args.hostclass
	if target_hostclass==None:
		target_hostclass=""
	else:
		target_hostclass=args.hostclass

	#cwd = os.getcwd()
	cwd = "/var/directory/manage_splunk"

	# Start logging data
	logFile = start_logging(cwd,target_hostname,update_user_configs,target_hostclass)

	# HACK TEst
	#yum_ready = base_yum_on_target_host(cwd,logFile,target_hostname)
	#stop_logging(logFile)
	#exit()

	#  Create a lock file to prevent more than one process working on the same host at the same time
	lockFile = set_lock(logFile,target_hostname,cwd)

	# Parse all the ops-config data and put into dictionaries
	ops_config_host_data, ops_config_hostclass_data = parse_ops_config(logFile,target_hostname,target_hostclass)

	# Get the name of the Splunk package from the ops_config data.
	splunk_pkg_name = splunk_ansible_pkg_exist(logFile,ops_config_hostclass_data)

	# If the Splunk-ansible package is not in ops_config, then no more work to do. We are done.
	# Otherwise, get all the splunk_ops_config data correcsponding to the target host
	# If the host can not be found in the splunk_ops_config file, then a placeholder/default host.yml will be created
	if (splunk_pkg_name!=""):
		splunk_ops_config_host_data = parse_splunk_ops_config(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_pkg_name)

		#  Check that the data from ops_config matches the id data in splunk_ops_config
		if sanity_check_configs(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_ops_config_host_data):

			#  Check that the enable bit and configuration window allow the push
			if push_allowed(splunk_ops_config_host_data):

				log_message(logFile,"Update window open.")
				if (debug): print "Update window open"

				#  Create the playbook
				if(create_playbook(cwd,logFile,target_hostname,ops_config_host_data,ops_config_hostclass_data,splunk_ops_config_host_data,update_user_configs)):

					#  At this point if the playbook is exists. Not if the playbook was created.
					if (update_user_configs == "T") or (update_user_configs == "D") or (update_user_configs == "L"):
						#  Run playbook
						command = []
						yum_ready = True
						if (update_user_configs == "D"):
							#  Make sure that the target host has a base yum capability
							yum_ready = base_yum_on_target_host(cwd,logFile,target_hostname)
						if (update_user_configs == "L"):
							command = ['/usr/local/bin/ansible-playbook','-i',target_hostname+",",cwd+"/splunk_playbooks/"+target_hostname+"/"+target_hostname+".yml",'-c','paramiko','-u','svc_configator']
						else:
							command = ['/usr/local/bin/ansible-playbook','-i',target_hostname+",",cwd+"/splunk_playbooks/"+target_hostname+"/"+target_hostname+".yml",'--private-key','/home/svc_configator/.ssh/id_rsa.pem']
						if (not yum_ready):
							log_message(logFile,"Will not attempt to run playbook. Cuz yum repo is not ready")
							if (debug): print "Will not attempt to run playbook. Cuz yum repo is not ready"
						else:
							log_message(logFile,str(command))
							if (debug): print str(command)
                        				output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        				stdout, stderr = output.communicate()
							log_message(logFile,"=============  Ansible Play ================")
							log_message(logFile,str(stdout))
							log_message(logFile,str(stderr))

							# Instead of printing out the entire playbook stdout, parse the data for issue.
							parse_playbook_exhaust(str(stdout))

						#  Splunk restart has been pulled out of the playbook, because is needs to be more intelligent and available
						#  The following uses an external script to detect Splunk state and change it if necessary
						if (update_user_configs == "T") or (update_user_configs == "L"):
							splunk_restart(cwd,logFile,ops_config_host_data,splunk_ops_config_host_data,target_hostname,stdout)
						else:
							if (debug): print "User opted to run the playbook. But Splunk will not be started or restarted."
							log_message(logFile,"User opted to run the playbook. But Splunk will not be started or restarted.")
							if (debug): print "Not going to detect config changes."
							log_message(logFile,"Not going to detect config changes.")

						print "Here"
						if (update_user_configs == "T") or (update_user_configs == "L"):
							print "Here1"
                					ops_config_host_data_params = ops_config_host_data['params']
                					ops_config_host_data_params_splunk = ops_config_host_data_params['splunk']
        						splunk_dir = ops_config_host_data_params_splunk['splunk_install_target_directory']
        						splunk_type = ops_config_host_data_params_splunk['splunk_type']
        						splunk_full_path = splunk_dir+splunk_type

							# Make sure that admin password is set correctly
							#print "Make ssure password is set"
							#password = set_admin_password(cwd,logFile,target_hostname,splunk_full_path)

							# Make sure that hostname and servername are correct
							# Restart splunk if needed.
							#ensure_hostname_is_correct(cwd,logFile,target_hostname,password,splunk_full_path)
						elif (update_user_configs == "D"):
							print ""
							print "sudo -u splunk tail -f /var/directory/splunk/var/log/splunk/splunkd.log"
							print "sudo -u splunk tail -f /var/directory/splunkforwarder/var/log/splunk/splunkd.log"
							print "sudo -u splunk /var/directory/splunk/bin/splunk status"
							print "sudo -u splunk /var/directory/splunkforwarder/bin/splunk status"
							print "python ./switch_splunks_on_host.py "+target_hostname+" nomove"
							print ""

						# As a pubic service announcement, tell inform the user the current state of Splunk on the host
						# python ./detect_splunk_state.py goods-product-review-app2.snc1
        					path_to_script = cwd+"/detect_splunk_state.py"
        					command = ['python',path_to_script,target_hostname]
        					log_message(logFile,str(command))
        					output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        					stdout, stderr = output.communicate()
        					log_message(logFile,str(stdout))
						print "\n\n"+str(stdout)+"\n\n"

					else:
						if (debug): print "User opted to NOT run the playbook."
						log_message(logFile,"User opted to NOT run the playbook.")

				else:
					log_message(logFile,"ERROR. Not able to create the playbook. Done for now.")
					if (debug): print "ERROR. Not able to create the playbook. Done for now."

			else:
				log_message(logFile,"Update window CLOSED. Done for now.")
				if (debug): print "Update window closed."

		else:
			log_message(logFile,"ERROR.  Something smells funny. Configs across ops-config and splunk-ops-config do not match.")
			if (debug): print "ERROR.  Something smells funny. Configs across ops-config and splunk-ops-config do not match."
	else:
		log_message(logFile,"This is not an Ansible managed host.  Bye.")
		if (debug): print "This is not an Ansible managed host.  Bye."

	stop_logging(logFile)

	remove_lock(lockFile)

	exit(0)


