#!/bin/bash

env=$1
sourcetype=$2
lookback=$3

if [ $1 == 'production' ] 
then
	curl -k -u admin:shoelaces66 https://splunk-api-snc1.snc1:8089/services/search/jobs/export -d search="search index=* sourcetype=$sourcetype earliest=$lookback | stats count by host | fields host" -d output_mode=csv
fi
