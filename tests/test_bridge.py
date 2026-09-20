import http.client,json,pathlib,socket,subprocess,sys,tempfile,time,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class BridgeTests(unittest.TestCase):
    def test_authentication_origin_and_idempotent_ingestion(self):
        with tempfile.TemporaryDirectory() as folder:
            sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
            script='from gold_workspace.bridge import serve; import sys; serve(sys.argv[1],int(sys.argv[2]))'
            process=subprocess.Popen([sys.executable,'-u','-c',script,folder,str(port)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                tokenfile=pathlib.Path(folder)/'bridge-token.txt'
                for _ in range(100):
                    if process.poll() is not None:raise RuntimeError('Bridge exited before listening')
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=.1):
                            if tokenfile.exists():break
                    except OSError:pass
                    time.sleep(.03)
                else:raise RuntimeError('Bridge did not become ready')
                token=tokenfile.read_text();payload=json.dumps({'format':'gold-collector','version':1,'posts':[{'key':'tester:123456','owner':'tester','id':'123456','text':'hello','sources':['likes']}]})
                def request(token_value,origin=None):
                    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+token_value}
                    if origin:headers['Origin']=origin
                    connection.request('POST','/ingest',payload,headers);response=connection.getresponse();result=response.status,json.loads(response.read());connection.close();return result
                self.assertEqual(request('wrong')[0],403)
                self.assertEqual(request(token,'https://evil.example')[0],403)
                self.assertEqual(request(token,'chrome-extension://'+'a'*32)[1]['added_versions'],1)
                self.assertEqual(request(token)[1]['added_versions'],0)
            finally:
                process.terminate();process.communicate(timeout=5)
if __name__=='__main__':unittest.main()
