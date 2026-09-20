"""Optional authenticated, loopback-only ingestion endpoint. No remote command execution."""
import hmac,http.server,json,pathlib,re,secrets
from .engine import Workspace

def serve(path,port=8766):
    root=pathlib.Path(path).resolve();root.mkdir(parents=True,exist_ok=True);keyfile=root/'bridge-token.txt'
    if not keyfile.exists():keyfile.write_text(secrets.token_urlsafe(32),encoding='utf-8')
    token=keyfile.read_text().strip()
    class Handler(http.server.BaseHTTPRequestHandler):
        def origin(self):
            value=self.headers.get('Origin')
            return value if value and re.fullmatch(r'chrome-extension://[a-p]{32}',value) else None
        def permitted(self):
            return self.headers.get('Host')==f'127.0.0.1:{port}' and (not self.headers.get('Origin') or self.origin())
        def send(self,status,value):
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store')
            if self.origin():self.send_header('Access-Control-Allow-Origin',self.origin());self.send_header('Vary','Origin')
            self.end_headers();self.wfile.write(json.dumps(value).encode())
        def do_OPTIONS(self):
            if not self.permitted():self.send(403,{'error':'Origin or Host rejected'});return
            self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.origin() or 'null');self.send_header('Access-Control-Allow-Methods','POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.end_headers()
        def do_POST(self):
            if not self.permitted() or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):self.send(403,{'error':'Not authorized'});return
            if self.path!='/ingest':self.send(404,{'error':'Not found'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=10_000_000:raise ValueError('Payload must be 1 byte to 10 MB')
                data=json.loads(self.rfile.read(size));w=Workspace(root)
                try:result=w.import_backup(data=data)
                finally:w.close()
                self.send(200,result)
            except Exception as e:self.send(400,{'error':str(e)})
        def log_message(self,*args):pass
    print(json.dumps({'status':'listening','url':f'http://127.0.0.1:{port}','token_file':str(keyfile),'scope':'Gold Collector backup ingestion only'}),flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
