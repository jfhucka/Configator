##################
#
#   This script looks in the logs directlry and cleans out log files that are older than X seconds
#
#################

import argparse
import os, sys, time
import subprocess

# Specify the maximum age of a file
num_days = 1

def get_file_directory(file):
	return os.path.dirname(os.path.abspath(file))


if __name__ == "__main__":

        parse = argparse.ArgumentParser(usage='%(prog)s ', description='Clean out the log files in the log directlry that are older than the allow time.')
        args = parse.parse_args()

	now = time.time()
	cutoff = now - (num_days * 86400)

	files = os.listdir(os.path.join(get_file_directory(__file__), "logs"))
	file_path = os.path.join(get_file_directory(__file__), "logs/")
	for xfile in files:
		if os.path.isfile(str(file_path) + xfile):
			t = os.stat(str(file_path) + xfile)
			c = t.st_ctime

			if c < cutoff:
				#print "Gonna remove "+ str(file_path) + xfile
				os.remove(str(file_path)+xfile)



