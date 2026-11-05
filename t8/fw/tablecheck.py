#!/usr/bin/env python3
"""exec/tablecheck.py on tok's tables, unchanged in logic: its folder is pointed at tok/, as cov.py does. Run through tokrun.py with T8_WRITES=1.

    T8_WRITES=1 python t8/fw/tokrun.py ../t8/fw/tablecheck.py --label writes --out t8/fw/results/tablecheck_writes.json
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
TOK = os.path.join(X210, "tok")
src = open(os.path.join(X210, "exec", "tablecheck.py")).read()
old = "HERE = os.path.dirname(os.path.abspath(__file__))"
assert src.count(old) == 1
src = src.replace(old, f"HERE = {TOK!r}")
sys.path.insert(0, TOK)
a = src.index("def program_path(c):")
b = src.index("def load_program(path):")
src = src[:a] + "def program_path(c):\n    import compile_ir as CI\n    h = hashlib.sha256(open(CI.__file__, 'rb').read())\n    for f in (core.__file__, ir_mod.__file__, S.__file__):\n        h.update(open(f, 'rb').read())\n    h.update(json.dumps(c.stats(), sort_keys=True).encode())\n    return os.path.join(HERE, 'build', f'program-{h.hexdigest()[:12]}.npz')\n\n\n" + src[b:]
exec(compile(src, os.path.join(TOK, "tablecheck.py"), "exec"), {"__name__": "__main__", "__file__": os.path.join(TOK, "tablecheck.py")})
