import json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
lock=json.loads((root/'source-lock.json').read_text())
dockerfile=(root/'Dockerfile').read_text()
assert 'FROM '+lock['go_base']+' AS build' in dockerfile
assert 'ARG TAILSCALE_COMMIT='+lock['upstream_commit'] in dockerfile
assert 'ARG TAILSCALE_VERSION='+lock['upstream_version'] in dockerfile
assert re.fullmatch('[a-f0-9]{40}',lock['upstream_commit'])
assert lock['platforms']==['linux/amd64']
workflow=root/'.github/workflows/image.yaml'
if workflow.exists():
 for action,sha in re.findall(r'uses:\s+([^@\s]+)@([^\s]+)',workflow.read_text()):
  assert lock['action_pins'].get(action)==sha,(action,sha)
  assert re.fullmatch('[a-f0-9]{40}',sha)
assert 'USER 65532:65532' in dockerfile
compose=(root/'compose.yaml').read_text()
assert '- -verify-clients' in compose and 'read_only: true' in compose
print('Source, base image, workflow pins and production verification settings checked.')
