"""Badge helper: load manifest and return inline image HTML for tokens.
"""
import base64
import json
import os
import sys

_manifest = None


def _load_manifest():
    global _manifest
    if _manifest is not None:
        return _manifest
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, 'assets', 'badges', 'manifest.json')
    if not os.path.exists(path):
        _manifest = {'tokens': {}}
        return _manifest
    with open(path, 'r', encoding='utf-8') as f:
        _manifest = json.load(f)
    return _manifest


def get_badge_html(token, size=14):
    m = _load_manifest()
    tokens = m.get('tokens', {}) if m else {}
    rel = tokens.get(token)
    if rel:
        # Resolve relative to bundle root (supports PyInstaller's _MEIPASS)
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        path = os.path.normpath(os.path.join(base, rel))
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                b64 = base64.b64encode(data).decode('ascii')
                ext = os.path.splitext(path)[1].lower().lstrip('.') or 'png'
                mime = 'image/png' if ext == 'png' else f'image/{ext}'
                return f"<img src='data:{mime};base64,{b64}' width='{size}' height='{size}' style='vertical-align:middle;'> "
            except Exception:
                pass
    # fallbacks
    if token == 'm':
        return "<span style='color:#9146FF;'>🛡️</span> "
    if token == 'v':
        return "<span style='color:#ffcc00;'>💎</span> "
    if token == 's':
        return "<span style='color:#FFD700;'>★</span> "
    return ''
