"""Optional Windows CPU-only install from the official pinned portable archive.
Requires: python -m pip install remotezip==0.12.6
Use on SSD. ZIP CRC is checked on extraction; per-file SHA256 is recorded.
"""
import argparse,hashlib,json
from pathlib import Path
import requests
from remotezip import RemoteZip,RemoteFetcher
URL='https://github.com/ollama/ollama/releases/download/v0.40.18/ollama-windows-amd64.zip?download=1'
class Fetch(RemoteFetcher):
    def get_file_size(self):
        # requests.head does not follow GitHub's redirect by default.
        res=requests.head(self._url,allow_redirects=True,timeout=60);res.raise_for_status()
        return int(res.headers['Content-Length'])
p=argparse.ArgumentParser();p.add_argument('destination',type=Path);a=p.parse_args();dest=a.destination.resolve();dest.mkdir(parents=True,exist_ok=True)
manifest={}
with RemoteZip(URL,fetcher=Fetch,support_suffix_range=False) as z:
    for info in z.infolist():
        if info.is_dir() or '/cuda_' in info.filename or '/vulkan/' in info.filename: continue
        target=(dest/info.filename).resolve()
        if not target.is_relative_to(dest): raise ValueError('Archive path escapes installation directory')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(z.read(info));manifest[info.filename]=hashlib.sha256(target.read_bytes()).hexdigest()
        print('Installed',info.filename,flush=True)
(dest/'installed-files.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
