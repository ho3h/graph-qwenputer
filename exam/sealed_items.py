#!/usr/bin/env python3
"""exam/AFTER.md S1: exam/items.py's items for a sealed map, on its blocking copy. Through tokrun: sealed_items.py --name MAP --out F"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import items as I  # noqa: E402

X = os.path.dirname(HERE)
I.load = lambda m: (os.path.join(HERE, "items", "sealed", m + "_b.graph.json"), os.path.join(X, "data", "heldout", m, m + ".questions.json"))
I.main()
