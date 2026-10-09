"""Read PyMuPDF's installed file identities without executing its PDF engine."""
import hashlib
import importlib.metadata
import json
from pathlib import Path

dist = importlib.metadata.distribution('pymupdf')
files = {}
for entry in dist.files or []:
    path = Path(dist.locate_file(entry))
    if path.is_file():
        files[str(entry)] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size}
print(json.dumps({'name': dist.metadata['Name'], 'version': dist.version,
                  'wheel_metadata': dist.read_text('WHEEL'),
                  'files': files,
                  'build_metadata': Path(dist.locate_file('pymupdf/_build.py')).read_text()}, indent=2))
