"""Frozen benchmark: time solve() on the frozen inputs and hash its outputs.

It prints one JSON line: {"metric": seconds, "outputs": sha256}.
The metric is CPU time of this process, so other load on the machine
adds less noise than wall time would.
"""

import hashlib
import json
import time

import target

with open("inputs.json") as handle:
    limits = json.load(handle)

start = time.process_time()
outputs = target.solve(limits)
seconds = time.process_time() - start

digest = hashlib.sha256(json.dumps(outputs).encode()).hexdigest()
print(json.dumps({"metric": seconds, "outputs": digest}))
