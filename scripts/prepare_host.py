"""Run with sudo on the new Linux host; create per-instance secrets outside the image."""
import argparse,hashlib,ipaddress,os,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--ip',required=True);p.add_argument('--image',required=True);a=p.parse_args()
ip=str(ipaddress.IPv4Address(a.ip))
assert re.fullmatch(r'ghcr\.io/[a-z0-9_.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}',a.image),'Use a verified immutable GHCR digest'
assert hasattr(os,'geteuid') and os.geteuid()==0,'Run this script with sudo on Linux'
root=Path(__file__).resolve().parents[1]
for rel in ['data/identity','data/derper','run','certs']:
 folder=root/rel;folder.mkdir(parents=True,exist_ok=True);os.chown(folder,65532,65532);folder.chmod(0o700)
key=root/'certs'/f'{ip}.key';crt=root/'certs'/f'{ip}.crt'
if not key.exists() and not crt.exists():
 subprocess.run(['openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes','-sha256','-days','30','-subj',f'/CN={ip}','-addext',f'subjectAltName=IP:{ip}','-keyout',str(key),'-out',str(crt)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
assert key.exists() and crt.exists(),'Incomplete certificate pair; inspect locally'
for f in (key,crt):os.chown(f,65532,65532);f.chmod(0o600)
env=root/'.env';env.write_text(f'DERP_IMAGE={a.image}\nDERP_HOSTNAME={ip}\nDERP_BIND_IP=0.0.0.0\n');env.chmod(0o600)
der=subprocess.check_output(['openssl','x509','-in',str(crt),'-outform','DER'])
print('Headscale DERP certificate pin: sha256-raw:'+hashlib.sha256(der).hexdigest())
print('Per-instance files prepared. Start identity, authorize it, then start derper.')
