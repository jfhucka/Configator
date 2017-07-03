##################
#
#   This script users Splunk cli commands to set the correct "hostname" on the specified server.
#   This fixes hosts that are incorrectly named without the colo. 
#   Hostname in Splink should be foo.snc1 NOT foo
#
#################

import argparse
import os
import time
import subprocess

if __name__ == "__main__":

        parse = argparse.ArgumentParser(usage='%(prog)s hostname splunk_full_path password', description='Set the Splunk instance on the specified host to the specified hostname.')
        parse.add_argument('hostname', nargs=1, help='The name of the host to apply Splunk configs. e.g. myhost.snc1')
	parse.add_argument('splunk_full_path', nargs=1, help='the path to the Splunk instance. e.g. /var/directory/splunk')
	parse.add_argument('password',nargs=1, help='The Splunk admin password')
        args = parse.parse_args()
        target_hostname = args.hostname[0]
	splunk_full_path = args.splunk_full_path[0]
	password = args.password[0]

	# sudo /var/directory/splunk/bin/splunk set default-hostname goods-product-review-app7.snc1 -auth admin:shoelaces66
        command = ['ssh',target_hostname,'sudo -u splunk '+splunk_full_path+'/bin/splunk set default-hostname '+target_hostname+' -auth admin:'+password]
        print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        print str(stdout)
        must_restart = False
        if "restart" in str(stdout): must_restart = True

        # sudo /var/directory/splunk/bin/splunk set servername goods-product-review-app7.snc1 -auth admin:shoelaces66
        command = ['ssh',target_hostname,'sudo -u splunk '+splunk_full_path+'/bin/splunk set servername '+target_hostname+' -auth admin:'+password]
        print str(command)
        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, stderr = output.communicate()
        print str(stdout)
        if "restart" in str(stdout): must_restart = True

	#  It appears Splunk ALWAYS says, restart. Even is the hostname has already been set.
	#  We really do not need to restart Splunk.
	must_restart = False
        if (must_restart):
                #  Is Splunk already running? Restart if needed. Otherwise keep splunk in its current state.
                command = ['ssh',target_hostname,'sudo -u splunk '+splunk_full_path+'/bin/splunk status']
                print str(command)
                output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                response, stderr = output.communicate()
		print str(response)
                if "not running" in response :
			print "Host was not running and will remain stopped."
                elif "running" in response:
			command = ['ssh',target_hostname,'sudo -u splunk '+splunk_full_path+'/bin/splunk restart']
                        output=subprocess.Popen(command,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        stdout, stderr = output.communicate()
                        print stdout
		print "Success"


