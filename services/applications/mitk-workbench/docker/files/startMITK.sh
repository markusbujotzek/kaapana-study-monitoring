#!/bin/bash
echo "Starting MITK Workbench"
/mitk/MitkWorkbench.sh &
PID=$!

tail -f $HOME/logfile | while read LOGLINE
do
	[[ "${LOGLINE}" == *"BlueBerry Workbench ready"* ]] && pkill -P $$ tail
done

echo 'Setting fullscreen mode'
wmctrl -r 'Research' -b toggle,fullscreen

wait $PID



