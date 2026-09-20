"""Start the local app and optional capture bridge; Ctrl+C stops owned processes."""
import pathlib
import socket
import subprocess
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gold_workspace.app import serve

if __name__=='__main__':
    bridge=None
    with socket.socket() as probe:
        running=probe.connect_ex(('127.0.0.1',8766))==0
    if not running:
        bridge=subprocess.Popen([sys.executable,'-m','gold_workspace','bridge'],cwd=ROOT)
    try:serve(ROOT/'workspace-data')
    finally:
        if bridge:
            bridge.terminate();bridge.wait(timeout=10)
