#!/usr/bin/env python3
"""exam/items_all.py on the mini, which has no transformers and gets no installs. items.py imports AutoTokenizer for its own main, which items_all doesn't call, so a stand-in satisfies the import. Through tokrun."""
import os
import runpy
import sys
import types

m = types.ModuleType("transformers")
m.AutoTokenizer = None
sys.modules["transformers"] = m
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import items  # noqa: E402

items.X.MODEL = os.environ["TOK_CKPT"]                              # the mini has the model's tokenizer in its meta folder, which gives the same tables
sys.argv[0] = os.path.join(HERE, "items_all.py")
runpy.run_path(sys.argv[0], run_name="__main__")
