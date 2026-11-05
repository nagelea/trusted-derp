"""Linux Docker integration checks. The temporary test ports bind localhost only."""
import argparse,hashlib,http.client,json,os,re,shutil,socket,ssl,struct,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--image',required=True);a=p.parse_args()
assert os.geteuid()==0,'Run with sudo; test directories are owned by runtime UID 65532'
root=Path(__file__).resolve().parents[1]
def run(args,check=True):
 r=subprocess.run(args,capture_output=True,text=True,timeout=90)
 if check and r.returncode:raise RuntimeError('Command failed: '+' '.join(args[:4])+'\n'+r.stderr[-1200:])
 return r
meta=json.loads(run(['docker','image','inspect',a.image]).stdout)[0]
assert meta['Config']['User']=='65532:65532'
assert meta['Architecture']=='amd64' and meta['Os']=='linux'
assert run(['docker','run','--rm',a.image,'--help']).returncode==0
version=run(['docker','run','--rm','--entrypoint','/usr/local/bin/tailscale',a.image,'version']).stdout.strip()
folder=Path(tempfile.mkdtemp(prefix='trusted-derp-test-'));cid=None
report={'image':a.image,'image_id':meta['Id'],'runtime_user':meta['Config']['User'],'client_version':version,'transport_test_authenticated':False}
try:
 certs=folder/'certs';state=folder/'state';certs.mkdir();state.mkdir()
 key=certs/'127.0.0.1.key';crt=certs/'127.0.0.1.crt'
 run(['openssl','req','-x509','-newkey','ec','-pkeyopt','ec_paramgen_curve:P-256','-nodes','-sha256','-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1','-keyout',str(key),'-out',str(crt)])
 for f in (certs,state,key,crt):os.chown(f,65532,65532);f.chmod(0o700 if f.is_dir() else 0o600)
 args=['docker','run','-d','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true','--tmpfs','/tmp','-p','127.0.0.1::8443/tcp','-p','127.0.0.1::13478/udp','-v',str(certs)+':/certs:ro','-v',str(state)+':/state',a.image,'-a=:8443','-hostname=127.0.0.1','-certmode=manual','-certdir=/certs','-c=/state/derper.json','-http-port=-1','-stun-port=13478']
 cid=run(args).stdout.strip();assert re.fullmatch('[0-9a-f]{64}',cid)
 port=int(run(['docker','port',cid,'8443/tcp']).stdout.strip().rsplit(':',1)[1])
 udp=int(run(['docker','port',cid,'13478/udp']).stdout.strip().rsplit(':',1)[1])
 ctx=ssl.create_default_context(cafile=str(crt))
 for attempt in range(30):
  try:
   conn=http.client.HTTPSConnection('127.0.0.1',port,context=ctx,timeout=2);conn.request('GET','/generate_204');status=conn.getresponse().status;conn.close();assert status==204;break
  except (OSError,AssertionError):
   if attempt==29:raise
   time.sleep(.25)
 report['https_verified_status']=status
 transaction=os.urandom(12)
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
  s.settimeout(3);s.sendto(struct.pack('!HHI12s',1,0,0x2112A442,transaction),('127.0.0.1',udp));data,_=s.recvfrom(2048)
 kind,length,cookie,reply_transaction=struct.unpack('!HHI12s',data[:20])
 assert kind==0x101 and cookie==0x2112A442 and reply_transaction==transaction and len(data)==20+length
 report['stun_binding_response_valid']=True
 run(['docker','cp',cid+':/usr/share/derp/build.json',str(folder/'build.json')])
 build=json.loads((folder/'build.json').read_text());lock=json.loads((root/'source-lock.json').read_text())
 assert build['upstream_commit']==lock['upstream_commit']
 assert build['upstream_version']==lock['upstream_version']
 report['upstream_build']=build
 report['production_auth_config']='Compose enables verify-clients; this local transport test does not enroll a Headscale device.'
 fake=folder/'compose.env';fake.write_text('DERP_IMAGE=ghcr.io/example/trusted-derp@sha256:'+'0'*64+'\nDERP_HOSTNAME=192.0.2.1\nDERP_BIND_IP=127.0.0.1\n')
 run(['docker','compose','--env-file',str(fake),'-f',str(root/'compose.yaml'),'config','--quiet'])
 report['compose_config_valid']=True
 (root/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:
 if cid and re.fullmatch('[0-9a-f]{64}',cid):run(['docker','rm','-f',cid],check=False)
 assert folder.parent==Path(tempfile.gettempdir()) and folder.name.startswith('trusted-derp-test-')
 shutil.rmtree(folder)
