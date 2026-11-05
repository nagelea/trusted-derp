"""Resolve an official Docker Hub base to an immutable OCI index digest."""
import hashlib,json,urllib.request
url='https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/golang:pull'
with urllib.request.urlopen(url,timeout=30) as r:token=json.load(r)['token']
req=urllib.request.Request('https://registry-1.docker.io/v2/library/golang/manifests/1.27.3-bookworm',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json'})
with urllib.request.urlopen(req,timeout=30) as r:
 data=r.read();digest=r.headers['Docker-Content-Digest']
assert digest=='sha256:'+hashlib.sha256(data).hexdigest()
print(json.dumps({'go_base':'docker.io/library/golang:1.27.3-bookworm@'+digest}))
