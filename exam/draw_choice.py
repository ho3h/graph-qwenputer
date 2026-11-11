#!/usr/bin/env python3
"""exam/AFTER.md R's draw. python3 exam/draw_choice.py"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
g = json.load(open(os.path.join(os.path.dirname(HERE), "data", "heldout", "nyc", "nyc.graph.json")))
import collections
c = collections.Counter(n["label"] for n in g["nodes"])
uniq = sorted(k for k, v in c.items() if v == 1)
rng = random.Random("20261108:nyc:choice")
A_T = ["How do I get from {a} to {b}?", "What's the best way from {a} to {b} on the subway?", "I'm at {a} and need to get to {b}. Which way?", "Fewest stops from {a} to {b}, please.", "Can you route me from {a} to {b}?"]
A = [A_T[i % 5].format(a=x, b=y) for i, (x, y) in enumerate(rng.sample(uniq, 2) for _ in range(30))]
B = ["Why is the New York subway so loud?", "When did the New York subway open?", "How much does a subway ride cost?", "Why are some subway lines lettered and others numbered?", "Is it safe to ride the subway at night?", "Who runs the New York subway?", "How do the subway's express trains work?", "Why is the subway so hot in summer?", "What does the MTA do?", "How deep is the deepest subway station in New York?", "What's the etiquette for standing on a subway escalator?", "Are there rats in the subway?", "Why do subway trains screech on curves?", "Can I bring a bike on the subway?", "Do subway trains run all night?", "What's OMNY?", "Who designed the subway map?", "Why does New York's map look different from London's?", "How many people ride the subway each day?", "What's a good subway book to read?", "Why are there so many delays on weekends?", "What happens when a subway station floods?", "Why do people like the old subway tiles?", "Is the subway map to scale?", "What should a tourist know about the subway?", "How do subway signals work?", "Why are subway cars different widths?", "What is a third rail?", "How is a subway different from a light rail?", "Is the subway better than driving in New York?"]
C = ["What's the capital of France?", "Write a haiku about autumn.", "What's 17 times 23?", "Who wrote Pride and Prejudice?", "How do I boil an egg?", "Why is the sky blue?", "What's a good name for a cat?", "Explain photosynthesis in one sentence.", "How many legs does a spider have?", "What's the largest ocean?", "Give me a tip for sleeping better.", "What does a noun do in a sentence?", "Who painted the Mona Lisa?", "How do vaccines work?", "Translate 'good morning' into Spanish.", "What's the boiling point of water?", "Write a one-line joke about Mondays.", "What is a black hole?", "How tall is Mount Everest?", "What's the difference between a virus and a bacterium?", "What should I cook for dinner?", "How do I fold a fitted sheet?", "What's the square root of 144?", "Who was Ada Lovelace?", "What's a good first programming language?", "What is inflation?", "How does a rainbow form?", "Name three primary colors.", "What's the speed of light?", "Why do cats purr?"]
D = ["How do I get from Paris to Lyon?", "What's the best way from Oxford Circus to King's Cross?", "Route me from Shibuya to Shinjuku.", "How do I get from Alexanderplatz to Potsdamer Platz?", "Fewest stops from Gare du Nord to Bastille, please.", "I'm at Union Station in Chicago and need O'Hare. Which way?", "Can you route me from Brixton to Camden Town?", "How do I get from Powell St to Embarcadero?", "What's the best way from Sagrada Familia to Barceloneta?", "Fewest stops from Dupont Circle to Foggy Bottom, please.", "How do I get from Akihabara to Ueno?", "Route me from Hollywood to Union Station in Los Angeles.", "I'm at Central in Hong Kong and need to reach Mong Kok. Which way?", "How do I get from Waterloo to Paddington?", "What's the best way from Sydney Central to Circular Quay?", "Can you route me from Kendall to Harvard in Boston?", "How do I get from Rome's Termini to the Colosseum?", "Fewest stops from Marienplatz to Sendlinger Tor, please.", "How do I get from Atocha to Sol?", "Route me from Bloor to Union in Toronto."]
chat = ["Hi! How's your day going?", "Thanks for the help earlier. Do you like trains?", "Can you recommend a good pizza topping?", "What's a fun fact about pigeons?", "I'm visiting New York next week. Any general advice?"]
E_ = []
for i in range(20):
    x, y = rng.sample(uniq, 2)
    E_.append([chat[i % 5], A_T[i % 5].format(a=x, b=y)])
conv = []
for arm, qs in (("A", A), ("B", B), ("C", C), ("D", D)):
    for i, q in enumerate(qs):
        conv.append({"key": f"{arm}:{i}", "graph": "nyc", "arm": arm, "turns": [{"user": q, "gold": "", "wants": None}]})
for i, t in enumerate(E_):
    conv.insert(i, {"key": f"E:{i}", "graph": "nyc", "arm": "E", "turns": [{"user": t[0], "gold": "", "wants": None}, {"user": t[1], "gold": "", "wants": None}]})
json.dump({"seed": 20261108, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "choice_draw.json"), "w"), ensure_ascii=False, indent=0)
print(len(conv), conv[0]["turns"][1]["user"], A[0])
