# bg-job.ps1 <job.sh> : run a bash job script detached, in hidden Git Bash, at BelowNormal priority (ffmpeg, node and
# Chrome started by it inherit the class), so a 4K conform / cut / render never freezes the Claude app on a low-memory PC
# and survives the Claude session ending. The job writes its own log; end it with a line like "ALLDONE" and watch the log
# (Monitor with tail -f | grep, or a background `until grep -q ALLDONE log; do sleep 2; done`).
#   powershell -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$SK/scripts/bg-job.ps1")" "$(cygpath -w "$W/jobs/<name>.sh")"
# Start the job script with `sleep 2` so the priority is set before its first heavy child starts.
param([string]$Job)
$p = Start-Process -FilePath "C:\Program Files\Git\bin\bash.exe" -ArgumentList @("`"$Job`"") -WindowStyle Hidden -PassThru
$p.PriorityClass = 'BelowNormal'
"started pid $($p.Id)"
