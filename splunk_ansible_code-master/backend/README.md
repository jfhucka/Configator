#splunk_ansible.py
    This script is a wrapper around Ansible.
    For a given host, it reads the ops-config files and the splunk-ops-config files found in the splunk repo.
    The script builds a playbook based on the information found in ops-config and runs that playbook against 
    the specified host. This script does NOT start or restart Splunk. That is accomplished outside the Ansible
    playbook by running change_splunk_state.py
    
#change_splunk_state.py
    This script starts, stops, or restarts Splunk on a specified host.
    Any "action" command line parameter is effectively passed to /bin/splunk <action> and executed.
    
#detect_splunk_state.py
    This script sends to stdout the current state of "splunk" and "splunkforwarder" on the specified host.
    The primamry value of this script is helping migrate a host from "splunk" to a "splunkforwarder".

#collect_configs.py
    This script logs into to a specified host and compares its configs with configs with configs that already exist
    in the splunk apps repo. The script populates a recommendation file in the recommendation directory on how
    to proceed. This script is a valuable tool needed to get all FWDer configs into the app repo for Ansible 
    management and delivery. Also, the recomendation file conatins valuable information for how to edit the 
    host.yaml file in prep for Ansible management.
    
#read_google_sheet.py
    This is a script that reads the Master sheet and returns the data via stdout. Typically, this script is used 
    by other scripts and the stdout data is parsed.
    
#change_index.py
    This script reads the Master sheet (with index<->sourcetype mappings), edits the inputs.conf file(s) on the
    Splunk host to include the new index name.
    
#splunk_manager_listener.py
    This script is meant to run 24x7 on the Ansible server. It listens to a specific port, and kicks off splunk_ansible.py
    with a host hits the specified port. In crontab ....
    */5 * * * * python /var/directory/manage_splunk/splunk_manager_listener.py
    
#collect_configs.py
    This script reaches out to a specified host and recommends any needed pushes to the splunk repo based on 
    the host's existing configs.
    
#get_hosts.py
    This script finds all the hosts that contribute to a specidied sourcename. The script runs a Splunk search command (found in get_hosts.sh) to list all the contributing hosts over the specified search window.

#splunk_push_configs.py
    This script is used to ping the Ansible server and ask for a config push. The script can either be run on the host
    with the FWDer. Similar to a rolled package. Or the script can be run on ANY host, given the specified name of the
    host that needs a pushed set of configs from the Ansible server.
    
#switch_splunks_on_host.py
    This script is used to facilitate the "stopping" of the SPLUNK instance and the "starting" of the SPLUNKFORWARDER instance 
    on a specified host.
    
#switch_splunks_on_host_at_specified_time.py
    This script is a wrapper around the "switch_splunks_on_host.py" to help make the switch between SPLUNK and SPLUNKFORWARDER
    at a specified time.
    
#update_apps_in_branch.py
    This script is 24x7 refresh of the "splunk_apps" git repo on the Ansible server. This helps ensure that any chnages made to the
    splunk_apps repo (master branch) git push down to the Ansible server for playbook inclusion.
    In crontab AS svc_configator user ...
    */10 * * * * /usr/local/bin/python /var/directory/manage_splunk/update_apps_in_branch.py

