import argparse,json,pathlib,sys
from .engine import Workspace
from .interface import catalog,invoke,serve_mcp

def main():
    parser=argparse.ArgumentParser(description='Gold agent research workspace. All output is JSON; use catalog for schemas.')
    parser.add_argument('--workspace',default=str(pathlib.Path(__file__).resolve().parents[1]/'workspace-data'))
    parser.add_argument('operation',choices=['catalog','mcp','bridge','app',* [t['name'] for t in catalog()]])
    parser.add_argument('--args',default='{}',help='JSON arguments')
    parser.add_argument('--args-file',help='UTF-8 JSON argument file')
    args=parser.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stdin,'reconfigure'):sys.stdin.reconfigure(encoding='utf-8')
    if args.operation=='mcp':serve_mcp(args.workspace);return
    if args.operation=='app':
        from .app import serve
        serve(args.workspace);return
    if args.operation=='bridge':
        from .bridge import serve
        serve(args.workspace);return
    if args.operation=='catalog':print(json.dumps(catalog(),ensure_ascii=False));return
    w=Workspace(args.workspace)
    try:
        arguments=json.loads(pathlib.Path(args.args_file).read_text(encoding='utf-8-sig') if args.args_file else args.args)
        print(json.dumps(invoke(w,args.operation,arguments),ensure_ascii=False,indent=2))
    except Exception as e:print(json.dumps({'error':str(e)},ensure_ascii=False));sys.exit(1)
    finally:w.close()
if __name__=='__main__':main()
