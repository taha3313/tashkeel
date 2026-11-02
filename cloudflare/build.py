"""Bundle the small, public frontend into a Cloudflare Worker module."""
import base64
import json
import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
assets = {}
for path in sorted((ROOT / 'static').rglob('*')):
    if not path.is_file():
        continue
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    if mime.startswith('text/') or mime in ('application/javascript', 'image/svg+xml'):
        mime += '; charset=utf-8'
    assets['/static/' + path.relative_to(ROOT / 'static').as_posix()] = [mime, base64.b64encode(path.read_bytes()).decode()]
assets['/'] = assets['/static/index.html']
output = ROOT / 'cloudflare/assets.generated.mjs'
output.write_text('export default ' + json.dumps(assets, separators=(',', ':')) + ';\n')
print(f'Bundled {len(assets)} paths into {output.name}')
