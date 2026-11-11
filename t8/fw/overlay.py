"""Import this first. Loads tok/'s boot_tok.py with two more header words for the noun (in memory; the file isn't changed), then tok/overlay.py as it stands.
   26 noun offset   27 noun length | has-the-field << 16
Nothing on disk under tok/, fw/, cop/ or vendor/ changes.
"""
import hashlib
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
TOK = os.path.join(X210, "tok")
for p in (os.path.join(X210, "vendor", "qwenputer-riscv"), os.path.join(X210, "lib"), os.path.join(X210, "host"), os.path.join(X210, "cop"), TOK, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
src = open(os.path.join(TOK, "boot_tok.py")).read()
BOOT_TOK_SHA = hashlib.sha256(src.encode()).hexdigest()
for old, new in (("HDR_WORDS, RELHASH, MAGIC = 26, 128, 0x30313258", "HDR_WORDS, RELHASH, MAGIC = 28, 128, 0x30313258"),
                 ("    hdr[:7] = [MAGIC,", "    _nb = (g.get('noun') or '').encode()\n    hdr[26] = put(_nb) if _nb else 0\n    hdr[27] = len(_nb) | int('noun' in g) << 16\n    hdr[:7] = [MAGIC,")):
    assert src.count(old) == 1, old
    src = src.replace(old, new)
_mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("boot_tok", loader=None))
_mod.__file__ = os.path.join(HERE, "boot_tok(patched)")
sys.modules["boot_tok"] = _mod
exec(compile(src, _mod.__file__, "exec"), _mod.__dict__)
_spec = importlib.util.spec_from_file_location("tok_overlay", os.path.join(TOK, "overlay.py"))
O = importlib.util.module_from_spec(_spec)
sys.modules["overlay_tok"] = O
_spec.loader.exec_module(O)
