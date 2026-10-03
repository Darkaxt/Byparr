"""Run fixture validation under hard resource limits, sharing immutable layers."""

import sys

from remote_ct import run

# ruff: noqa: INP001 - standalone operator script

program = r"""
import subprocess, json
name='byparr-post-validation'
old=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
if old.returncode==0:
    info=json.loads(old.stdout)[0]
    assert info['Config']['Labels']['io.darkaxt.byparr.task']=='post-fork'
    assert not info['State']['Running']
    subprocess.run(['docker','rm',name],check=True)
subprocess.run(['docker','build','--network=none','--pull=false','-f','/opt/byparr-custom/Dockerfile.custom','-t','local/byparr-post:validation','/opt/byparr-custom'],check=True)
base='local/byparr-post:validation'
cmd=['docker','run','--rm','--name',name,'--label','io.darkaxt.byparr.task=post-fork',
'--cpus','0.5','--memory','1g','--memory-swap','1g','--pids-limit','256',
'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
'--restart','no','--no-healthcheck','--log-opt','max-size=5m','--log-opt','max-file=2',
'--env','HOME=/tmp','--env','PYTHONPATH=/app',
'--tmpfs','/tmp:rw,nosuid,nodev,size=256m,mode=1777','--shm-size','256m',
'--tmpfs','/cache/invisible-playwright/fonts:rw,nosuid,nodev,size=8m,uid=1000,gid=1000',
'--tmpfs','/cache/invisible-playwright/geoip:rw,nosuid,nodev,size=128m,uid=1000,gid=1000',
'--tmpfs','/cache/mozilla:rw,nosuid,nodev,size=8m,uid=1000,gid=1000',
'--tmpfs','/cache/fontconfig:rw,nosuid,nodev,size=8m,uid=1000,gid=1000',
'--tmpfs','/cache/mesa_shader_cache:rw,nosuid,nodev,size=16m,uid=1000,gid=1000',
'--mount','type=bind,src=/opt/byparr-custom/tests,dst=/app/tests,readonly',
'--entrypoint','/app/.venv/bin/python',base,'/app/tests/SCRIPT']
result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
print('\n'.join(line for line in result.stdout.splitlines() if not line.startswith('2026-') or 'pw:browser' not in line),flush=True)
from pathlib import Path
Path('/opt/byparr-custom/SCRIPT.log').write_text(result.stdout)
raise SystemExit(result.returncode)
"""
script = (
    "redirect_integration.py" if "--redirects" in sys.argv else "browser_integration.py"
)
if "--challenges" in sys.argv:
    script = "challenge_integration.py"
raise SystemExit(run(program.replace("SCRIPT", script)).returncode)
