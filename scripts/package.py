"""Package the extension, excluding the private index and all personal backups."""
import pathlib, zipfile
root=pathlib.Path(__file__).resolve().parents[1]
with zipfile.ZipFile(root/'gold-collector-extension.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in (root/'extension').rglob('*'):
        if path.is_file() and path.name!='personal-index.json':
            archive.write(path,path.relative_to(root))
    archive.write(root/'THIRD_PARTY.md','THIRD_PARTY.md')
print('Packaged extension; personal index and backups excluded.')
