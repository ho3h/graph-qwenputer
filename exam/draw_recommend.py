#!/usr/bin/env python3
"""exam/AFTER.md V2's draw. python3 exam/draw_recommend.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
W = ["New York is adding one new subway line that links two existing stations directly. Which two far-apart stations should it connect to save riders the most stops? Answer with the two station names.",
     "If you could build one new express link between two subway stations in New York, which two would save riders the most stops? Answer with the two station names.",
     "The MTA can add a single new direct connection between two stations. Which pair would cut the most stops from people's trips? Answer with the two station names.",
     "Pick two New York subway stations that are many stops apart and should be joined by a new line. Answer with the two station names.",
     "Which two New York stations are poorly connected today, and would most benefit from a new direct line between them? Answer with the two station names.",
     "You're planning New York's next subway line. It runs directly between two existing stations. Which two do you choose, to save the most stops overall? Answer with the two station names.",
     "Use the subway map to suggest one new direct line between two stations that would shorten trips the most. Answer with the two station names.",
     "Where should a new New York subway line go, as a direct link between two existing stations? Answer with the two station names.",
     "Find two stations far apart on the map, and propose a new direct line between them. Answer with the two station names.",
     "A new line connects two existing stations with no stops between. Name the two stations you'd pick to help the most riders."]
conv = [{"key": f"nyc-rec:{i}", "graph": "nyc", "turns": [{"user": w, "gold": "open", "wants": None}]} for i, w in enumerate(W)]
json.dump({"seed": 20261104, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "recommend_draw.json"), "w"), ensure_ascii=False, indent=0)
