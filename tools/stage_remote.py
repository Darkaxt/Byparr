"""Transfer the small source/fixture packet, never dependencies or browser files."""

import base64
from pathlib import Path

from remote_ct import run

# ruff: noqa: INP001 - standalone operator script

root = Path(__file__).resolve().parents[1]
paths = [
    root / "main.py",
    *sorted((root / "src").glob("*.py")),
    *sorted((root / "tests").glob("*integration.py")),
    root / "Dockerfile.custom",
    root / "compose.custom.yaml",
    root / "runtime/patch_firefox_redirects.py",
]
packet = {
    p.relative_to(root).as_posix(): base64.b64encode(p.read_bytes()).decode()
    for p in paths
}
source = """
import base64, json, pathlib, subprocess, hashlib
root=pathlib.Path('/opt/byparr-custom')
root.mkdir(exist_ok=True)
existing=subprocess.run(['docker','inspect','byparr-custom'],capture_output=True,text=True)
if existing.returncode==0:
    instance=json.loads(existing.stdout)[0]
    assert instance['Config']['Labels']['io.darkaxt.byparr.task']=='post-fork'
    assert not instance['State']['Running'], 'Stop the test instance before staging'
baseline=root/'production-baseline.json'
if not baseline.exists():
    containers=json.loads(subprocess.check_output(['docker','inspect','byparr','prowlarr']))
    snapshot={c['Name']: {'id':c['Id'],'image':c['Image'],'startedAt':c['State']['StartedAt'],'restartCount':c['RestartCount']} for c in containers}
    snapshot['composeSha256']=hashlib.sha256(pathlib.Path('/opt/byparr/compose.yaml').read_bytes()).hexdigest()
    snapshot['serveSha256']=hashlib.sha256(subprocess.check_output(['tailscale','serve','status','--json'])).hexdigest()
    baseline.write_text(json.dumps(snapshot,indent=2)+'\\n')
for name, content in PACKET.items():
    path=root/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(base64.b64decode(content))
    path.chmod(0o644)
print('Transferred',len(PACKET),'source/fixture files,',sum(len(base64.b64decode(v)) for v in PACKET.values()),'bytes')
""".replace("PACKET", repr(packet))
raise SystemExit(run(source).returncode)
