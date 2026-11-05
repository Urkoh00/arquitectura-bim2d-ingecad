"""Write .arqbim contracts from the user's DXF (+ one variant with a door and a window)."""
from pathlib import Path
import sys, json
import ezdxf
from arquitectura import exchange
from arquitectura.architectural import metadata, _xdata
OUT = str(Path(__file__).resolve().parents[1] / 'out') + '/'
for name in ('34', '35', '36'):
    doc = ezdxf.readfile(f'tests/dxf/{name}.dxf')
    d = exchange.write(doc, OUT + f'{name}.arqbim', project=f'Prueba {name}')
    print(name, len(d['elements']), 'elementos | avisos:', d['issues'])
# variant: 36 + a door and a window in the bottom wall of the left room
doc = ezdxf.readfile('tests/dxf/36.dxf'); msp = doc.modelspace()
wall = next(e for e in msp if (metadata(e) or {}).get('id') == '5b0d184647b74dfa8c2ce023d70cfcb3')
import uuid
for off, w, sill, h, kind in ((3.0, 0.9, 0.0, 2.1, 'door'), (8.0, 1.5, 0.9, 1.2, 'window')):
    p = msp.add_point((10 + off + w/2, 5), dxfattribs={'layer': 'ARQ-HUECOS3D'})
    _xdata(msp, p, {'kind': 'opening', 'schema': 1, 'id': uuid.uuid4().hex,
                    'wall_id': '5b0d184647b74dfa8c2ce023d70cfcb3', 'offset': off,
                    'width': w, 'sill': sill, 'height': h, 'type': kind})
doc.saveas(OUT + '36_huecos.dxf')
d = exchange.write(doc, OUT + '36_huecos.arqbim', project='Prueba 36 con huecos')
print('36_huecos', len(d['elements']), 'elementos | huecos:', sum(len(e.get('openings', [])) for e in d['elements']))
