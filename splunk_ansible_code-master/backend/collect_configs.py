################################################
#
#    This is a tool intended to be used by Splunk Ops to aid in the FWDer migration to Ansible.
#
#    Given a specific host, this script will help create:
#       1.  ops_config params
#       2.  splunk_ops_config host.yml file
#       3.  user apps, admin apps, and admin system configs for the splunk_ansible git repo
#
#    This script was intended to be run ONCE on a host with an existing Splunk FWDer.
#    The script output is intended to remove most (all?) of the work required to migrate an existing Splunk FWDer to be Ansible mamanged
#
#    A.  ssh into a host and find the running splunk instance
#    B.  scp back into the same host and get all the apps and the /etc/system/local and /etc/apps/search/local configs
#    C.  compare all apps to see if there is an app with teh same name and identical contents
#    D.  compare the /etc/system/local configs with contents of other admin_system configs
#    E.  compare the /etc/search/local with the set of search_app configs
#    F.  Output a recommended set of commands to mv apps into the git repo
#    G.  Create a recommended host.yml with params for ops-config and a host.yml for splunk_ops_config
#
###############################################


#  Lock bit location relative to location of this script.
lockBitLocation = "lockDirectory"
logFileLocation = "logs"
urlConfigHost = "http://config/host"
#urlConfigHostclass = "http://config/hostclass"
urlSplunkConfigHost = "https://raw.github.com/splunk/splunk_ops_config/master"

app_black_list = ['introspection_generator_addon','learned','search','SplunkUniversalForwarder','framework','gettingstarted','legacy','sample_app','splunk_archiver','SplunkForwarder','SplunkLightForwarder','launcher','splunk_datapreview','appsbrowser','splunkbeta','splunk_management_console']
#system_local_black_list = ['README','server.conf']
conf_black_list = ['README','server.conf','deploymentclient.conf','serverclass.conf','distsearch.conf','eventtypes.conf','tenants.conf','web.conf','migration.conf']
illegal_config_files = ['props.conf','transforms.conf']

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
import stat

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
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'sudo ls -1 /var/directory/splunk*/bin/splunk']
        #if (debug): print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()	
	splunk_lines = stdout.split()
	for item in splunk_lines:
		command = ['ssh',target_hostname,'sudo '+item+' status']
		#if (debug): print str(command)
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        	stdout, stderr = output.communicate()
		status_split = stdout.split("\n")
		#if (debug): print str(status_split)
		if "splunkd is running" in status_split[0]:
			segments = item.split("/")
			splunk_home = "/"+segments[1]+"/"+segments[2]+"/"+segments[3]+"/"
			return(splunk_home)
	return("")


def get_apps(cwd,target_hostname,splunk_home,whoiam):

	#  Copy all apps in the /etc/app directory into a local directory on this server
	#  Filter apps that come shipped with Splunk FWDer


	#  Remove all apps out of the local repository
	command = ['rm','-rf',cwd+'/user_apps/'+target_hostname+'/*']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()

	#  Get list of apps in /etc/apps
	command = ['ssh',target_hostname,'ls -1 '+splunk_home+'etc/apps']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	splunk_lines = stdout.split()
	for item in splunk_lines:
		if item in app_black_list:
			print "Skip app: "+item
			continue
		
		# Make sure the /user_apps directory has a repository for this host
		user_app_dir_name = cwd+"/user_apps/"+target_hostname
		if not os.path.isdir(user_app_dir_name):
                	os.makedirs(user_app_dir_name)
                	if (debug): print "Created user app directory "+user_app_dir_name

		# Remove the app dir form /tmp
		# Copy the app dir to /tmp
		# Chown the /tmp/app
		# scp the /tmp/app to the local user_apps directory
		command = ['ssh',target_hostname,'sudo rm -rf /tmp/'+item]
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		if stderr != None:
			print "ERROR: "+command
			print str(stdout)
			print str(stderr)
			return(False)
		command = ['ssh',target_hostname,'sudo cp -r '+splunk_home+'etc/apps/'+item+' /tmp/'+item]
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		if stderr != None:
			print "ERROR: "+command
			print str(stdout)
			print str(stderr)
			return(False)
		command = ['ssh',target_hostname,'sudo chown -R '+whoiam+':'+whoiam+' /tmp/'+item]
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		if stderr != None:
			print "ERROR: "+command
			print str(stdout)
			print str(stderr)
			return(False)
		command = ['scp','-r',target_hostname+':/tmp/'+item,cwd+'/user_apps/'+target_hostname]
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		if stderr != None:
			print "ERROR: "+command
			print str(stdout)
			print str(stderr)
			return(False)	
		print "Collected user app named: "+item
	return(True)



#
#  The search_app has become the repository for all misc configs found in apps/search/local, apps/launcher/local, apps/learned/loca
#      apps/SplunkForwarder/local, apps/SplunkLightForwarder/local
#

def get_search_app(cwd,target_hostname,splunk_home,whoiam):

        #  Copy all configs in the /etc/app/search/local directory into a local directory on this server

	# Make sure the /search_app directory has a repository for this host
	search_app_dir_name = cwd+"/search_app/"+target_hostname
	if not os.path.isdir(search_app_dir_name):
		os.makedirs(search_app_dir_name)
		if (debug): print "Created search app directory "+search_app_dir_name

	command = ['ssh',target_hostname,'sudo rm -rf /tmp/search_app']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	if stderr != None:
		print "ERROR: "+command
		print str(stdout)
		print str(stderr)
		return(False)

	command = ['ssh',target_hostname,'sudo mkdir /tmp/search_app']
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        command = ['ssh',target_hostname,'sudo cp -r '+splunk_home+'etc/apps/launcher/local/* /tmp/search_app/']
	#print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
	#print str(stdout), str(stderr)
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        command = ['ssh',target_hostname,'sudo cp -r '+splunk_home+'etc/apps/SplunkLightForwarder/local/* /tmp/search_app/']
        #print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        #print str(stdout), str(stderr)
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        command = ['ssh',target_hostname,'sudo cp -r '+splunk_home+'etc/apps/learned/local/* /tmp/search_app/']
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	#print str(command)
        stdout, stderr = output.communicate()
	#print str(stdout), str(stderr)
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        command = ['ssh',target_hostname,'sudo cp -r '+splunk_home+'etc/apps/SplunkForwarder/local/* /tmp/search_app/']
	#print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
	#print str(stdout), str(stderr)
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

	command = ['ssh',target_hostname,'sudo cp -r '+splunk_home+'etc/apps/search/local/* /tmp/search_app/']
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout), str(stderr)
	if stderr != None:
		print "ERROR: "+command
		print str(stdout)
		print str(stderr)
		return(False)

        #  Not all config files should be allowed.
        for item in conf_black_list:
                command = ['ssh',target_hostname,'sudo rm -rf /tmp/search_app/'+item]
                output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                stdout, stderr = output.communicate()
	#  Remove any config that does not end with .conf
	#  sudo find /var/directory/splunkforwarder/etc/system/local -type f ! -name '*.conf' -delete
	command = ['ssh',target_hostname,"sudo find /tmp/search_app -type f ! -name '*.conf' -delete"]
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	print "Cleaned up the configs"


	command = ['ssh',target_hostname,'sudo chown -R '+whoiam+':'+whoiam+' /tmp/search_app']
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout), str(stderr)
	if stderr != None:
		print "ERROR: "+command
		print str(stdout)
		print str(stderr)
		return(False)

	command = ['scp',target_hostname+':/tmp/search_app/*',cwd+'/search_app/'+target_hostname+'/']	
	#print str(command)
	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout, stderr = output.communicate()
	#print str(stdout), str(stderr)
	if stderr != None:
		print "ERROR: "+command
		print str(stdout)
		print str(stderr)
		return(False)

	print "Collected search app local configs"	

        return(True)




def get_system(cwd,target_hostname,splunk_home,whoiam):

        #  Copy all configs in the /etc/system/local directory into a local directory on this server

        # Make sure the /system_local directory has a repository for this host
        system_dir_name = cwd+"/system_local/"+target_hostname
        if not os.path.isdir(system_dir_name):
                os.makedirs(system_dir_name)
                if (debug): print "Created system local directory "+system_dir_name

        command = ['ssh',target_hostname,'sudo rm -rf /tmp/system_local']
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        command = ['ssh',target_hostname,'sudo cp -r '+splunk_home+'etc/system/local /tmp/system_local/']
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        command = ['ssh',target_hostname,'sudo chown -R '+whoiam+':'+whoiam+' /tmp/system_local']
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        command = ['scp',target_hostname+':/tmp/system_local/*',cwd+'/system_local/'+target_hostname+'/']     
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        if stderr != None:
                print "ERROR: "+command
                print str(stdout)
                print str(stderr)
                return(False)

        print "Collected system local configs"   

	#  Not all config files in /etc/system/local should be considered.
	for item in conf_black_list:
		command = ['rm','-rf',cwd+'/system_local/'+target_hostname+'/'+item]
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
        #  Remove any config that does not end with .conf
        #  sudo find /var/directory/splunkforwarder/etc/system/local -type f ! -name '*.conf' -delete
	command = "find "+cwd+"/system_local/"+target_hostname+"/ -type f ! -name *.conf -delete"
	#print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=True)
        stdout, stderr = output.communicate()
	print str(stdout)
	print "Cleaned up the system local configs"
    
        return(True)



def compare_user_apps(cwd,target_hostname):

	# For each app in the user_apps directory:
	#     - Does the app already exist in either the /splunk_ansible/user_apps or splunk_ansible/admin_apps directories
	#	- Apps are compared by NAME only. Not internal diff of all config files
	#     - Any identical apps should be put into the match_app list
	#     - Apps that have not match should be put into a recommend rename and add list

	user_app_list = []

	print "\nCompare user apps ...."
	print "======================="

        #  Get list of apps in user_apps
	app_dir_name = cwd+"/user_apps/"+target_hostname
        command = ['ls','-1',app_dir_name]
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
	print str(stdout)
        splunk_lines = stdout.split()
	no_match_app_list = []
	match_app_list = []
        for app in splunk_lines:

		user_app_repo = cwd+"/splunk_apps/user_apps/"
		# Does this an app by this exact name exist in the user_app directory?
		command = ['ls','-1',user_app_repo+app]
		look_in_admin_repo=0
		try:
			output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			stdout, stderr = output.communicate()
			if "No such file or directory" in str(stdout):
				look_in_admin_repo=1
			else:
				#print "stdout=>"+str(stdout)
				print "The app "+app+" was found in the user_app repo. No need to push to repo."
				match_app_list.append(app)
		except:
			look_in_admin_repo=1

		if look_in_admin_repo==1:
			look_in_admin_repo=0
			#print "The app can not be found in "+user_app_repo+app
			#  App user app by same name is not found. Look for the app in the admin apps repo
			admin_app_repo = cwd+"/splunk_apps/admin_apps/"
			command = ['ls','-1',admin_app_repo+app]
			try:
				output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
				stdout, stderr = output.communicate()
				if "No such file or directory" in str(stdout):
					print "Apparently the app "+app+" is not in user_apps or admin_apps"
					no_match_app_list.append(app)
				else:
					print "The app "+app+" was found in teh admin_app repo. Not need to push to repo."
					match_app_list.append(app)
			except:
				print "Apparently the app "+app+" is not in user_apps or admin_apps"
				no_match_app_list.append(app)
	

	print "Done processing all the user apps on the FWDer."
	print "matches="+str(match_app_list)
	print "no matches="+str(no_match_app_list)

	return(match_app_list,no_match_app_list)



def compare_sys_configs(cwd,target_hostname):

	# Find an app in the splunk_ansible/admin_system_configs that has 
	#    - the exact same number of configs as in system_local/splunk1-dev.snc1 directory
	#    - each config in system_local/splunk1-dev.snc1 is identical to the corresponding config in splunk_ansible/admin_system_configs

	print "\nCompare system local configs ...."
	print "======================="

	# Count the number of .conf files in the system_local/splunk1-dev.snc1 directory
	configs_path = cwd+'/system_local/'+target_hostname+'/'
	number_of_copied_conf_files = len([name for name in os.listdir(configs_path) if os.path.isfile(name)])

	#print "Number of config files found in system local = "+str(number_of_copied_conf_files)

	match_app = []
	no_match_app = []
        admin_sys_repo = cwd+"/splunk_apps/admin_system_configs/"
	# Generate a list of all apps in this dir
        command = ['ls','-1',admin_sys_repo]
        #print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        #print str(stdout)
	splunk_lines = stdout.split()
 
	found=0 
	for sys_app in splunk_lines:
		# Check to see if that dir has an identical number of conf files
		configs_path_repo = admin_sys_repo+sys_app
		number_of_conf_files = len([name for name in os.listdir(configs_path_repo) if os.path.isfile(name)])
		#print "Number of config files found in system app "+sys_app+" in repo = "+str(number_of_conf_files)
		if number_of_conf_files == number_of_copied_conf_files:
			#print "The number of config files match."

			# Check that each conf file is identical:
			os.chdir(configs_path)
			list_of_conf_files = glob.glob("*.conf")
			no_diff = 1
			for conf_file in list_of_conf_files:
				command = ['sudo','diff','-rq',configs_path+conf_file,configs_path_repo+"/"+conf_file]
				#print str(command)
				output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
				stdout, stderr = output.communicate()
				#print str(stdout)
				if len(stdout) != 0:
					#print "Detected difference between configs"
					no_diff = 0
					break	
			if no_diff == 1:
				#  At this point all configs match
				match_app.append(sys_app)
				found=1
				break
		else:
			# Number of conf files is differrent. So the apps are not identical.
			#print "The number of config files differs.  Move on ..."
			pass

	if found == 0:
		print "No matching system local app."
	        create_app = target_hostname+".system_local"
                no_match_app.append(create_app)

	print "Done processing all the system local configs on the FWDer."
        print "matches="+str(match_app)
        print "no matches="+str(no_match_app)


	# Finished comparing configs will all the configs in the repo
	return(match_app,no_match_app)




def compare_search_configs(cwd,target_hostname):

	#  We are moving all /etc/apps/search/local configs out of the search app and into user apps.
	#  Therefore try and find a user app that matches the search local configs

	print "\nCompare search local configs ...."
	print "======================="

	# Count the number of .conf files in the 
	configs_path = cwd+'/search_app/'+target_hostname+'/'
	#number_of_copied_conf_files = len([name for name in os.listdir(configs_path) if os.path.isfile(name)])
	number_of_copied_conf_files = len(glob.glob(configs_path+'*.conf'))
	#print "The number of config files found in "+configs_path+" is = "+str(number_of_copied_conf_files)
	#print str(glob.glob(configs_path+'*.conf'))

        match_app = []
	no_match_app = []

	if number_of_copied_conf_files > 0:
		user_app_repo = cwd+"/splunk_apps/user_apps/"
		# Generate a list of all apps in this dir
		command = ['ls','-1',user_app_repo]
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		stdout_list = stdout.split()
		#print str(stdout_list)

		found=0
		for user_app in stdout_list:
			#print "Compare with "+user_app
			# Check to see if that dir has an identical number of conf files
			configs_path_repo = user_app_repo+user_app+"/local"
			try:
				number_of_conf_files = len(glob.glob(configs_path_repo+'/*.conf'))
			except:
				number_of_conf_files = 0
			#print "     .... number of config files in app = "+str(number_of_conf_files)
			if (number_of_conf_files == number_of_copied_conf_files) and (number_of_conf_files > 0) :
			
				# Check that each conf file is identical:
				os.chdir(configs_path)
				list_of_conf_files = glob.glob("*.conf")
				diff=0
				for conf_file in list_of_conf_files:
					command = ['diff','-rq',configs_path_repo+'/'+conf_file,configs_path+"/"+conf_file]
                                	#print str(command)
                                	output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                                	stdout, stderr = output.communicate()
					#print str(stdout)
					if ("No such file or directory" in str(stdout)) or ("differ" in str(stdout)):
						print "Detected difference between configs"
						diff=1
						break
				if diff==0:
                        		#  At this point all configs match
                        		match_app.append(user_app)
					found=1
					break
                	else:
                        	# Number of conf files is differrent. So the apps are not identical.
                        	pass

		if found == 0:
			create_app = target_hostname+".search"
			no_match_app.append(create_app)


        # Finished comparing configs will all the configs in the repo
        print "Done processing all the search local configs on the FWDer."
        print "matches="+str(match_app)
        print "no matches="+str(no_match_app)

        return(match_app,no_match_app)



def find_illegal_config_files(cwd,target_hostname):

	#  Look in user_apps for illegal config files.
	search_directory = cwd+'/user_apps/'+target_hostname
	os.chdir(search_directory)
	for illegal_file in illegal_config_files:
		illegals = glob.glob(illegal_file)
		if len(illegals) != 0:
			print "How can this be a Forwarder?"
			print "There is a "+illegal_file+" in the user apps directory "+str(illegals)
			return(False)
	print ("No illegal files in user_apps")

	#  Look in the search app
	search_directory = cwd+'/search_app/'+target_hostname+'/'
	os.chdir(search_directory)
	for illegal_file in illegal_config_files:
                illegals = glob.glob(illegal_file)
                if len(illegals) != 0:
                        print "How can this be a Forwarder?"
                        print "There is a "+illegal_file+" in the search app "+str(illegals)
			return(False)
	print ("No illegal files in the search app")

	#  Look in the systems local directory
	search_directory = cwd+'/system_local/'+target_hostname+'/'
	os.chdir(search_directory)
        for illegal_file in illegal_config_files:
                illegals = glob.glob(illegal_file)
                if len(illegals) != 0:
                        print "How can this be a Forwarder?"
                        print "There is a "+illegal_file+" in the systems local "+str(illegals)
                        return(False)
	print ("No illegal files in system/local")

	return(True)
	




def build_recommendations(cwd,target_hostname,match_user_app_list,no_match_user_app_list,match_admin_system_configs_list,no_match_admin_system_configs_list,match_search_local_list,no_match_search_local_list,target_hostclass,whoiam):

	#  In cwd+/recommendations+target_hostname ...
	#     Create a host.yml file
	#     Create a file with a list of cammands to mv copied configs into new apps in repo
	#     Create a file/table of app <=> app


	#  Make sure the directory exists ...
        recommend_path = cwd+'/recommendations'
	if not os.path.isdir(recommend_path):
		os.makedirs(recommend_path)
	recommend_path = cwd+'/recommendations/'+target_hostname
        if not os.path.isdir(recommend_path):
                os.makedirs(recommend_path)
		print "Created "+recommend_path


	#  Build the host.yml file
        type="splunkforwarder"
	env = "production"
	host_split = target_hostname.split(".")
        colo = host_split[1]
        template_name = "default_"+type+"_"+env+"."+colo+".yml"

        url = urlSplunkConfigHost+"/"+template_name

        try:
                req=urllib2.Request(url)
                req.add_header('accept', 'application/x-yaml')
                r = urllib2.urlopen(req)
                new_host = yaml.load(r.read())

        except urllib2.HTTPError, e:
                if(debug): print "HTTP error"
                if(debug): print e.args
		if(debug): print "url="+str(url)
                exit(7)
        except urllib2.URLError, e:
                if(debug): print "URL error"
                if(debug): print e.args
                stop_logging(logFile)
                exit(8)

	url = urlConfigHost+"/"+target_hostname

	try:
                req=urllib2.Request(url)
                req.add_header('accept', 'application/x-yaml')
                r = urllib2.urlopen(req)
                orig_host = yaml.load(r.read())

        except urllib2.HTTPError, e:
                if(debug): print "HTTP error"
                if(debug): print e.args
                if(debug): print "url="+str(url)
                exit()
        except urllib2.URLError, e:
                if(debug): print "URL error"
                if(debug): print e.args
                stop_logging(logFile)
                exit()

	transfer_id = orig_host['id']

        #  Populate the template file
        new_host['hostname']=host_split[0]
        new_host['hostclass']=target_hostclass
        new_host['id']=transfer_id
        new_host['creation_timestamp']=time.strftime("%Y-%m-%d %H:%M:%S")
        new_host['update_window_start_date']=time.strftime("%Y-%m-%d")
        new_host['update_window_stop_time']="00:00:00"

        # Pick the latest "template_generic_v" from the splunk ops_config playbook repo
        template_list = glob.glob(cwd+"../manage_splunk/splunk_playbooks/template_generic_v*")
        latest_version=1
        try:
                for playbook in template_list:
                        version = playbook.split("template_generic_v")[1]
                        if int(version) > latest_version: latest_version=int(version)
                target_playbook = "template_generic_v"+str(latest_version)
        except:
                if(debug): print "Exception:"+str(template_list)
                target_playbook = "template_generic_v1"
        new_host['playbook_template'] = target_playbook

	#  Add recommended apps
	#  Note:  The search_local_list gets folded into user apps
	#  Note:  For user apps, if there is not match, then need assume an app is created by the same name
	user_app_list = match_user_app_list
	user_app_list.extend(no_match_user_app_list)
	user_app_list.extend(match_search_local_list)
	user_app_list.extend(no_match_search_local_list)

	# Do not put the user app list in the splunk_ops_config repo.
	# There should only be one 1 source for user apps, and that is in the ops-config repo
	#new_host['user_apps'] = user_app_list

	admin_system_configs_list = list(match_admin_system_configs_list)
	admin_system_configs_list.extend(no_match_admin_system_configs_list)
	new_host['admin_system_configs'] = admin_system_configs_list

        # Create a file and push that file up to splunk/splunk_ansible
	new_host_yml_name_full_path = recommend_path+"/"+target_hostname+".yml"

        try:
                f = open(new_host_yml_name_full_path, "w")
                f.write(yaml.dump(new_host))
                f.close()
		print "\n******** Check out data in the recommendations directory !!"
	except:
		print "ERROR.  Not able to write to "+new_host_yml_name_full_path
		exit(56)

	#  Create a table of all apps for this host
	new_host_yml_name_full_path = recommend_path+"/app_map_table"
	try:
		f = open(new_host_yml_name_full_path, "w")
	except:
		print "ERROR.  Not able to write to "+new_host_yml_name_full_path
                exit(57)


	#f.write("##### Matched user apps ######\n")
	for item in match_user_app_list:
		f.write(item+" == "+item+"\n")
	#f.write("##### Need to create these user apps\n")
	for item in no_match_user_app_list:
		f.write(item+" >>> "+item+"\n")
	#f.write("##### Config found in /etc/apps/search/local can be found in .... ####\n")
	for item in match_search_local_list:
		f.write("/etc/apps/search/local/* == "+item+"\n")
	#f.write("##### Config found in /etc/apps/search/local need to be moved to a new app .... ###\n")
	for item in no_match_search_local_list:
		f.write("/etc/apps/search/local/* >>> "+item+"\n") 
	#f.write("##### Config found in /etc/system/local can be found in .... ####\n")	
	for item in match_admin_system_configs_list:
		f.write("/etc/system/local/* == "+item+"\n")
	#f.write("##### Config found in /etc/system/local need to be moved to a new app .... ###\n")
	for item in no_match_admin_system_configs_list:
		f.write("/etc/system/local/* >>> "+item+"\n")
	f.close()


	#  Create a list of commands needed to create new apps in the repo
	command_path = recommend_path+"/commands.sh"
	try:
                f = open(command_path, "w")
        except:
                print "ERROR.  Not able to write to "+command_path
                exit(58)

	f.write("#!/bin/bash\n")
	do_something=False
	for item in no_match_user_app_list:
		do_something=True 
		src = cwd+"/user_apps/"+target_hostname+"/"+item
		dst = cwd+"/splunk_apps/user_apps"
		f.write("cp -r "+src+" "+dst+"\n")

	for item in no_match_search_local_list:
		do_something=True
		src = cwd+"/search_app/"+target_hostname+"/*"
		dst = cwd+"/splunk_apps/user_apps/"+item
		f.write("mkdir "+dst+"\n")
		f.write("mkdir "+dst+"/local\n")
		f.write("cp "+src+" "+dst+"/local/\n")

	for item in no_match_admin_system_configs_list:
		do_something=True
		src = cwd+"/system_local/"+target_hostname+"/*"
		dst = cwd+"/splunk_apps/admin_system_configs/"+item
		f.write("mkdir "+dst+"\n")
		f.write("cp "+src+" "+dst+"/\n")

	src = recommend_path+"/"+target_hostname+".yml"
	dst = cwd+"/splunk_ops_config/"
	f.write("cp "+src+" "+dst+"\n")
	f.close()
	st = os.stat(command_path)
	os.chmod(command_path,st.st_mode | stat.S_IEXEC)

	#  Create a host.yml file with edits needed to ops-config/hosts/host.yml file
	command_path = recommend_path+"/host.yml"
	try:
                f = open(command_path, "w")
        except:
                print "ERROR.  Not able to write to "+command_path
                exit(558)
	f.write("vi "+target_hostname+".yml\n\n")
	f.write("hostclass: "+target_hostclass+"\n\n")
	f.write("params:\n")
	f.write("  splunk:\n")
	f.write("    install_user_name: splunk\n")
	f.write("    number_of_splunk_instances_to_install: 1\n")
	f.write("    rpm_name: splunkforwarder-6.5.3-36937ad027d4.x86_64.rpm\n")
	f.write("    splunk_boot_start: True\n")
	f.write("    splunk_install_target_directory: /var/directory/\n")
	f.write("    splunk_type: splunkforwarder\n")
	f.write("    user_apps:\n")
	for item in user_app_list:
		f.write("    - "+item+"\n")
	f.write("\n\nusers:\n")
	f.write("- c_cstearns: {login_as: [svc_configator], sudo: true}\n")
	f.write("- jhuckabay: {login_as: [svc_configator], sudo: true}\n")
	f.write("- jsermersheim: {login_as: [svc_configator], sudo: true}\n")
	f.write("- nstearns: {login_as: [svc_configator], sudo: true}\n")
	f.write("- svc_configator: {sudo: true}\n")
	f.close()


        # Create an executable script that pushes the new apps into the master repo
        command_path = recommend_path+"/push_apps.sh"
        try:
                f = open(command_path, "w")
        except:
                print "ERROR.  Not able to write to "+command_path
                exit(58)
        f.write("#!/bin/bash\n")
        do_something=False
        f.write("cd ../../splunk_apps\n")
	f.write("sudo chown -R "+whoiam+":"+whoiam+" .\n")
        f.write("git pull --no-edit\n")
        f.write("git add .\n")
	f.write("sudo git add .\n")
        f.write('sudo git commit -m "Initial harvest of splunk apps from '+target_hostname+'"\n')
        f.write('git push\n')
	f.write('sudo git push\n')
	f.write("sudo chown -R "+whoiam+":"+whoiam+" .\n")
        f.write('cd ../splunk_ops_config\n')
	f.write("sudo chown -R "+whoiam+":"+whoiam+" .\n")
        f.write('git pull --no-edit\n')
        f.write('git add .\n')
	f.write("sudo git add .\n")
        f.write('sudo git commit -m "Initial harvest of splunk ops configs from '+target_hostname+'"\n')
        f.write('git push\n')
	f.write('sudo git push\n')
	f.write("sudo chown -R "+whoiam+":"+whoiam+" .")
        f.close()
        st = os.stat(command_path)
        os.chmod(command_path,st.st_mode | stat.S_IEXEC)
	

	if (do_something):
		print "Achtung - Not all the host configs are in the repo.  Please refer to the commands file in the recommendation directory."
	else:
		print "All configs for this host exist in the repo."

	return()

def is_sox_managed_host(target_hostname):
        # Browse to the http://config/host/hostname
        # Setup the header so that data is returned in a yaml format
        url = urlConfigHost+"/"+target_hostname

        try:
                req=urllib2.Request(url)
                req.add_header('accept', 'application/x-yaml')
                r = urllib2.urlopen(req)
                ops_config_host_data = yaml.load(r.read())
                #if(debug): print str(ops_config_host_data)
        except urllib2.HTTPError, e:
                if(debug): print "HTTP error"
                if(debug): print e.code
                stop_logging(logFile)
                exit(1)
        except urllib2.URLError, e:
                if(debug): print "URL error"
                if(debug): print e.args
                stop_logging(logFile)
                exit(2)

	try:
		params = ops_config_host_data['ops_params']
		regulatory_domains = params['regulatory_domains']
		if "sox" in str(regulatory_domains):
			#  This is a SOX managed host
			return(True)
		else:
			return(False)
	except:
		return(False)

	

if __name__ == "__main__":

#    First .... check to see if this is a SOX managed host.
#    A.  ssh into a host and find the running splunk instance
#    B.  scp back into the same host and get all the apps and the /etc/system/local and /etc/apps/search/local configs
#    C.  compare all apps to see if there is an app with teh same name and identical contents
#    D.  compare the /etc/system/local configs with contents of other admin_system configs
#    E.  compare the /etc/search/local with the set of search_app configs
#    F.  Output a recommended set of commands to mv apps into the git repo
#    G.  Create a recommended host.yml with params for ops-config and a host.yml for splunk_ops_config

	
	# Parse arguments   
	parse = argparse.ArgumentParser(usage='%(prog)s hostname hostclass', description='Gather FWDer configs from the specified host.')
	parse.add_argument('hostname', nargs=1, help='The name of the host that has the Splunk FWDer configs. e.g. myhost.snc1')
	parse.add_argument('hostclass', nargs=1, help='The name of the hostclass that this host belongs to.')
	args = parse.parse_args()
	target_hostname = args.hostname[0]
	target_hostclass = args.hostclass[0]

	#  Create a lock file to prevent more than one process working on the same host at the same time
	cwd = os.getcwd()
	lockFile = set_lock(target_hostname,cwd)

	# Check to see if this is a SOX managed host
	sox_managed = is_sox_managed_host(target_hostname)
	if (sox_managed):
		print "*******  THIS IS A SOX MANAGED HOST **********"
		print "    - It will not be possible to push configator managed configs to this host"
		print "    - Abort"
		print ""
		remove_lock(lockFile)
		exit()

	#  Check to see if this host is accessible
	command = ['ssh','-o','StrictHostKeyChecking no',target_hostname,'echo Hello']
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
	if "Hello" not in stdout:
		print "*******  THIS HOST IS NOT ACCESSIBLE VIA SSH  **********"
		print "    - It will not be possible to push configator managed configs to this host"
                print "    - Abort"
                print ""
                remove_lock(lockFile)
                exit()

	# Get to the target host and find Splunk Home. Home is were "/bin/splunk status" is running.  
	splunk_home = get_splunk_home(cwd,target_hostname)
	if splunk_home != "":
		if (debug): print "Splunk Home is "+splunk_home

		command = ['whoami']
		output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout, stderr = output.communicate()
		whoiam = "".join(stdout.split())
		print "Welcome "+whoiam

		#  scp back into the same host and get all the apps and the /etc/system/local and /etc/apps/search/local configs
		print "#########   USER APPS #############"
		success1=get_apps(cwd,target_hostname,splunk_home,whoiam)
		print "#########   SEARCH APPS #############"
		success2=get_search_app(cwd,target_hostname,splunk_home,whoiam)
		print "#########  SYSTEM/LOCAL CONFIGS #############"
		success3=get_system(cwd,target_hostname,splunk_home,whoiam)

		#  Check to see if there are any non_FWDer type of configs in the apps that were copied over. 
		#  If props.conf exists, then tell user and stop!
		no_issues = find_illegal_config_files(cwd,target_hostname)
		# Proceed even if illegal configs are found ...
		#if (no_issues):
		if 1==1:
			#print "No issues with the types of .conf files found in the FWDer."
			if (success1 and success2 and success3):
				# compare all apps to see if there is an app with the same name and identical contents
				match_user_app_list,no_match_user_app_list = compare_user_apps(cwd,target_hostname)
				match_admin_system_configs_list,no_match_admin_system_configs_list = compare_sys_configs(cwd,target_hostname)
				match_search_local_list,no_match_search_local_list = compare_search_configs(cwd,target_hostname)

				build_recommendations(cwd,target_hostname,match_user_app_list,no_match_user_app_list,match_admin_system_configs_list,no_match_admin_system_configs_list,match_search_local_list,no_match_search_local_list,target_hostclass,whoiam)
				print "SUCCESS. Done. Bye."

			else:
				print "There was a problem getting the apps and cofigs off the Splunk FWDer.  Bye."
		else:

			print "There were illegal configs found in the Splunk instance running on "+target_hostname
			print "This requires human intervention."
			print "Bye."

	else:
		print "Splunk is not running on this host. Not sure which configs to harvest. Bye!"
	
	remove_lock(lockFile)

	exit(0)


