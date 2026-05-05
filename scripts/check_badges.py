import os
import json
import importlib.util

# Load the project's badges.py explicitly to avoid name collision with the
# top-level `badges/` assets directory.
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
badges_py = os.path.join(proj_root, 'badges.py')
if os.path.exists(badges_py):
    spec = importlib.util.spec_from_file_location('project_badges', badges_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    get_badge_html = getattr(mod, 'get_badge_html')
else:
    get_badge_html = None

MANIFEST = os.path.join('assets', 'badges', 'manifest.json')

def main():
    if not os.path.exists(MANIFEST):
        print('Manifest not found at', MANIFEST); return
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        m = json.load(f)
    tokens = m.get('tokens', {})
    for t in ('m','v','s'):
        rel = tokens.get(t)
        path = os.path.normpath(rel) if rel else None
        exists = os.path.exists(path) if path else False
        print(f"token={t!r} rel={rel!r} path={path!r} exists={exists}")
        try:
            html = get_badge_html(t, size=14)
            print(f"html startswith: {html[:80]!r}")
        except Exception as e:
            print('get_badge_html error for', t, e)

if __name__ == '__main__':
    main()
