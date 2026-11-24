"""Follow-up check: S5 without pooling (the phased plan leaves pooling until last).
Run after experiments.py; writes results/extra.json."""
import json, os
from concurrent.futures import ProcessPoolExecutor
import config as C
from experiments import run_all, ci, OUT

if __name__ == "__main__":
    th, h = json.load(open(os.path.join(OUT, "best.json")))["65"]
    k = dict(dispatch="adaptive", gate_quota=True, reposition=True, theta=th, hold=h, load_cap=65)
    with ProcessPoolExecutor() as ex:
        r = run_all(ex, {"S5": (C.BASE, C.Policy(pooled=True, **k)), "S5N": (C.BASE, C.Policy(**k))}, range(30))
    ms = ("peak_mean", "peak_lost", "worst_route", "PM_GATE_mean", "km")
    d = {"S5N": {m: ci(r["S5N"][m]) for m in ms}, "S5N-S5": {m: ci(r["S5N"][m] - r["S5"][m]) for m in ms}}
    json.dump(d, open(os.path.join(OUT, "extra.json"), "w"), indent=1)
    print(d)
