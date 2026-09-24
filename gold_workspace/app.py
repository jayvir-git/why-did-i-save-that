"""Same-origin, loopback-only local application. Never serves workspace directories."""
import json
import pathlib
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .engine import Workspace
from .interface import invoke

ALLOWED = {'source_action','save_note','action_outcome','queue_review','save_review','source_targets','workspace_status','start_work','work_status','cancel_work','save_source_action','source_actions','inventory','search_library','research_search','result','get','investigate','artifact','claim','read_artifact','connect_research','request_media','media_requests','complete_media','enrichment_status','visual_queue'}


def server(workspace, port=8768):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, mime='application/json'):
            data = body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',mime+('; charset=utf-8' if not mime.startswith('image/') else ''))
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers(); self.wfile.write(data)

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host(): return self.send(403,{'error':'Loopback host required'})
            if re.fullmatch(r'/media/obs_[a-f0-9]{64}',self.path):
                w=Workspace(workspace)
                try:
                    item=w.get([self.path.split('/')[-1]])[0]['raw']
                    mime=item.get('mime','');blob=item.get('raw_blob','')
                    if mime not in ('image/png','image/jpeg','image/webp','image/gif') or not re.fullmatch(r'[a-f0-9]{64}',blob):
                        return self.send(404,{'error':'No supported cached image'})
                    return self.send(200,(w.path/'blobs'/blob).read_bytes(),mime)
                except (ValueError,FileNotFoundError):return self.send(404,{'error':'Image unavailable'})
                finally:w.close()
            assets={'/':('app.html','text/html'),'/app.js':('app.js','application/javascript'),'/app.css':('app.css','text/css')}
            if self.path not in assets: return self.send(404,{'error':'Not found'})
            name,mime=assets[self.path]
            self.send(200,(pathlib.Path(__file__).parent/'web'/name).read_bytes(),mime)

        def do_POST(self):
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or self.headers.get('Origin')!=origin or self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.send(403,{'error':'Same-origin JSON required'})
            if self.path!='/api': return self.send(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2_000_000: raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(length))
                if data.get('operation') not in ALLOWED: raise ValueError('Operation unavailable in web app')
                w=Workspace(workspace)
                try: result=invoke(w,data['operation'],data.get('args',{}))
                finally: w.close()
                self.send(200,result)
            except (ValueError,KeyError,TypeError,IndexError) as e: self.send(400,{'error':str(e)})
            except Exception as e: self.send(500,{'error':str(e)})

        def log_message(self,*args): pass
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def serve(workspace):
    app=server(workspace)
    print('Gold workspace: http://127.0.0.1:8768',flush=True)
    try: app.serve_forever()
    except KeyboardInterrupt: pass
    finally: app.server_close()
