
########
#
#   Given the host name and optionally the serverclass name, this method parses relevant data form the ops_config host file
#   and associated hostclass file.
#
#######

import urllib2
import yaml
import os
import argparse

urlConfigHost = "http://config/host"

if __name__ == "__main__":

        parse = argparse.ArgumentParser(usage='%(prog)s hostname ', description='Check to see if the ops-config/host.yml configs ahve been pushed and are now available.')
        parse.add_argument('hostname', nargs=1, help='The name of the host to apply Splunk configs. e.g. myhost.snc1')
        args = parse.parse_args()
        target_hostname = args.hostname[0]

        cwd = os.getcwd()
	url = urlConfigHost+"/"+target_hostname

        try:
                req=urllib2.Request(url)
                req.add_header('accept', 'application/x-yaml')
                r = urllib2.urlopen(req)
                ops_config_host_data = yaml.load(r.read())
        except urllib2.HTTPError, e:
                print e.code
                exit(1)
        except urllib2.URLError, e:
                print e.args

	try:
		foo = str(ops_config_host_data['params']['splunk']['rpm_name'])
		print "This host is ready to be managed by Splunk Ansible"
	except:
		print "This host is NOT ready to be managed by Splunk Ansible"



