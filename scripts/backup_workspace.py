"""Consistent SQLite backup plus immutable evidence. No bridge credentials included."""
import datetime
import pathlib
import sqlite3
import sys
import tempfile
import zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gold_workspace import Workspace

def backup(folder):
    folder=pathlib.Path(folder).resolve()
    output=folder/'backups';output.mkdir(exist_ok=True)
    target=output/('gold-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.zip')
    partial=target.with_suffix('.zip.partial')
    w=Workspace(folder)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db=pathlib.Path(tmp)/'workspace.sqlite'
            dest=sqlite3.connect(db)
            try:w.db.backup(dest)
            finally:dest.close()
            with zipfile.ZipFile(partial,'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.write(db,'workspace.sqlite')
                for path in sorted(folder.rglob('*')):
                    relative=path.relative_to(folder)
                    if not path.is_file() or path.is_symlink() or relative.parts[0]=='backups' or path.name.startswith('workspace.sqlite') or 'token' in path.name.casefold() or path.suffix=='.tmp':continue
                    z.write(path,relative.as_posix())
    finally:w.close()
    partial.replace(target)
    return target

if __name__=='__main__':print(backup(ROOT/'workspace-data'))
