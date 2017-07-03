#!/bin/bash

SSHAGENT=`which ssh-agent`
SSHAGENTARGS="-s"
if [ -z "$SSH_AUTH_SOCK" -a -x "$SSHAGENT" ]; then
    eval `$SSHAGENT $SSHAGENTARGS`
    trap "kill $SSH_AGENT_PID" 0
fi

sudo -u svc_ansible /usr/local/bin/git --git-dir=/var/directory/manage_splunk/splunk_playbooks/.git --work-tree=/var/directory/manage_splunk/splunk_playbooks push &>/var/directory/manage_splunk/logs/refresh_playbook_repo-$(date +%Y%m%d%H%M%S)

