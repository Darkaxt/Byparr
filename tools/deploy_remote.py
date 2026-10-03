"""Deploy only the separately named, limited test service in CT120."""

from remote_ct import run

# ruff: noqa: INP001 - standalone operator script

raise SystemExit(
    run(r"""
import json, subprocess, pathlib
root=pathlib.Path('/opt/byparr-custom')
assert json.loads((root/'production-baseline.json').read_text())['/byparr']['image']=='sha256:874f719518f617d03a60e03411fc5d090647e1a877041e81f8dc965927c7deb6'
existing=subprocess.run(['docker','inspect','byparr-custom'],capture_output=True,text=True)
if existing.returncode==0:
    x=json.loads(existing.stdout)[0]
    assert x['Config']['Labels']['io.darkaxt.byparr.task']=='post-fork'
    assert not x['State']['Running'], 'Do not replace a running test instance'
subprocess.run(['docker','build','--network=none','--pull=false','-f',str(root/'Dockerfile.custom'),'-t','local/byparr-post:custom-post',str(root)],check=True)
subprocess.run(['docker','compose','-f',str(root/'compose.custom.yaml'),'up','-d','--pull','never'],check=True)
stream=subprocess.Popen(['docker','logs','--follow','byparr-custom'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
ready=False
for line in stream.stdout:
    print(line.rstrip(),flush=True)
    if 'Application startup complete' in line:
        ready=True
        break
stream.terminate()
stream.wait()
assert ready, 'API startup did not complete'
x=json.loads(subprocess.check_output(['docker','inspect','byparr-custom']))[0]
h=x['HostConfig']
assert h['NanoCpus']==500000000 and h['Memory']==1073741824 and h['MemorySwap']==1073741824
assert h['PidsLimit']==256 and h['ReadonlyRootfs'] and h['RestartPolicy']['Name']=='no'
assert h['PortBindings']['8191/tcp']==[{'HostIp':'127.0.0.1','HostPort':'8192'}]
assert x['Config']['User']=='1000' and h['CapDrop']==['ALL'] and 'no-new-privileges:true' in h['SecurityOpt']
assert x['Config']['Healthcheck']['Test']==['NONE']
assert h['LogConfig']['Config']=={'max-file':'2','max-size':'5m'}
proof={'image':x['Image'],'containerId':x['Id'],'hostConfig':{k:h[k] for k in ['NanoCpus','Memory','MemorySwap','PidsLimit','ReadonlyRootfs','RestartPolicy','PortBindings','Tmpfs','CapDrop','SecurityOpt','LogConfig']}}
(root/'deployment-evidence.json').write_text(json.dumps(proof,indent=2))
print(json.dumps(proof,indent=2))
""").returncode
)
