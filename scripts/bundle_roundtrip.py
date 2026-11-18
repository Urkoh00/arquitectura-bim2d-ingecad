# SPDX-License-Identifier: GPL-3.0-or-later
"""Bundle the exact plugin geometry, never a second implementation."""
from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1];source=root/'arquitectura';target=root/'ingetrazo_ext/arq_shared'
target.mkdir(exist_ok=True)
(target/'__init__.py').write_text('# SPDX-License-Identifier: GPL-3.0-or-later\n')
files=['roundtrip_model.py','architectural.py','exchange.py','openings.py','cabinets.py','curved_carpentry.py','wall_categories.py']
files += [str(p.relative_to(source)) for p in (source/'geom').glob('*.py')]
manifest={}
for name in files:
 p=target/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,p);manifest[name]=hashlib.sha256(p.read_bytes()).hexdigest()
(target/'MANIFEST.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
