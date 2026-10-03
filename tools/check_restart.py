"""Prepare/verify a saved block across the normal launcher stop/start cycle."""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.red_side import RedSide


def state():
    with urlopen('http://127.0.0.1:8766/api/state', timeout=8) as response:
        return json.load(response)


def action(name, body=None):
    request = Request('http://127.0.0.1:8767/ui/' + name, data=json.dumps(body or {}).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=20) as response:
        return response.read().decode()


evidence_file = ROOT / 'runtime/restart-checks.json'
if sys.argv[1] == 'prepare':
    before = state()
    assert not before['blocks'], 'Existing build retained; restart test refused'
    action('place', {'block': 'minecraft:cobblestone', 'x': 0, 'y': 0, 'z': 0})
    saved = state()
    assert saved['inventory']['minecraft:cobblestone'] == before['inventory']['minecraft:cobblestone']-1
    evidence_file.write_text(json.dumps({'before': before, 'saved': saved}, indent=2))
    print('Prepared real MC block and saved its inventory state.')
elif sys.argv[1] == 'verify':
    evidence = json.loads(evidence_file.read_text())
    loaded = state()
    assert loaded == evidence['saved'], (loaded, evidence['saved'])
    action('reconnect')
    origin = json.loads((ROOT / 'runtime/bridge-origin.json').read_text())
    red = RedSide()
    hit = red.ground(origin['x'], origin['y']+5, origin['z'])
    assert 0.75 < hit['y']-origin['y'] < 1.25
    action('break', {'x': 0, 'y': 0, 'z': 0})
    cleaned = state()
    assert cleaned['inventory'] == evidence['before']['inventory'] and not cleaned['blocks']
    evidence.update({'loaded': loaded, 'native_hit_after_restore': hit, 'cleaned': cleaned,
                     'checks': ['normal MC shutdown', 'inventory/revision/block survive restart',
                                'restored native collider', 'test block removed and materials returned']})
    evidence_file.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
else:
    raise SystemExit('Expected prepare or verify')
