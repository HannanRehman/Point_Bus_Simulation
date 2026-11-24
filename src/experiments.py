"""Runs every experiment in the report and writes results/*.json.

    python experiments.py            full study (30 replications)
    python experiments.py --quick    smoke test (3 replications)
"""
import argparse, itertools, json, os, time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import numpy as np
from scipy import stats
import config as C
import model as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
P, B = C.Policy, C.BASE


def one(a):
    return M.simulate(*a)


def run_all(ex, jobs, seeds):
    """jobs: {name: (System, Policy)} -> {name: {metric: array over seeds}}"""
    args = [(s, p, k) for s, p in jobs.values() for k in seeds]
    res = list(ex.map(one, args, chunksize=2))
    n, out = len(seeds), {}
    for i, name in enumerate(jobs):
        block = res[i * n:(i + 1) * n]
        out[name] = {k: np.array([float(m[k]) for m in block]) for k in block[0]}
    return out


def ci(x):
    x = np.asarray(x)
    h = stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else 0.0
    return [float(x.mean()), float(h)]


def summary(res, base=None):
    s = {n: {k: ci(v) for k, v in m.items()} for n, m in res.items()}
    if base:                                  # paired differences (common random numbers)
        for n, m in res.items():
            s[n]["_diff"] = {k: ci(m[k] - res[base][k]) for k in m}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    q = ap.parse_args().quick
    n = 3 if q else 30
    eval_seeds = range(n)
    tune_seeds = range(1000, 1000 + (2 if q else 10))     # never reused for evaluation
    sens_seeds = range(2000, 2000 + (2 if q else 15))
    os.makedirs(OUT, exist_ok=True)
    save = lambda name, d: json.dump(d, open(os.path.join(OUT, name), "w"), indent=1)
    full = dict(dispatch="adaptive", pooled=True, gate_quota=True, reposition=True)
    t0 = time.time()
    with ProcessPoolExecutor() as ex:
        # 1. tuning: load trigger x hold x load limit
        grid = {}
        for cap, th, h in itertools.product((65, 78), (.75, 1.0, 1.25, 1.5), (5, 10, 15, 20, 30, 40)):
            if th * B.seats <= cap + .5:
                grid[f"{cap}|{th}|{h}"] = (B, P(**full, theta=th, hold=h, load_cap=cap))
        g = run_all(ex, grid, tune_seeds)
        save("grid.json", {k: {m: float(v[m].mean()) for m in
             ("peak_mean", "overcrowd", "km", "peak_lost", "worst_route")} for k, v in g.items()})
        best = {}
        for cap in (65, 78):
            ks = [k for k in g if k.startswith(str(cap))]
            w = {k: g[k]["peak_mean"].mean() for k in ks}
            near = [k for k in ks if w[k] <= 1.02 * min(w.values())]
            # shortest hold within 2% of the best; ties broken by wait
            b = min(near, key=lambda k: (int(k.split("|")[2]), w[k]))
            best[cap] = (float(b.split("|")[1]), float(b.split("|")[2]))
        save("best.json", {str(k): v for k, v in best.items()})
        print("best (theta, hold):", best, round(time.time() - t0), "s", flush=True)

        # 2. scenarios
        a = dict(theta=best[78][0], hold=best[78][1])
        c = dict(theta=best[65][0], hold=best[65][1], load_cap=65)
        more = replace(B, alloc=(11, 10, 8, 5))
        sc = {
            "S0": (B, C.S0),
            "S0R": (B, P(retimed=True)),
            "S1": (B, P(dispatch="adaptive", **a)),
            "S2": (B, P(dispatch="adaptive", gate_quota=True, **a)),
            "S3": (B, P(dispatch="adaptive", gate_quota=True, pooled=True, **a)),
            "S4": (B, P(**full, **a)),
            "S5": (B, P(**full, **c)),
            "S6": (B, P(**full, **c, stagger=15)),
            "W1": (more, P(retimed=True)),
            "W2": (B, P(gate_quota=True)),
            "W3": (B, P(stagger=15)),
            "W4": (B, P(load_cap=65)),
            "W5": (more, P(**full, **c)),
            "W6": (B, P(**full, **a, stagger=15)),
        }
        rs = run_all(ex, sc, eval_seeds)
        save("scenarios.json", summary(rs, "S0"))
        pairs = [("S1", "S0R"), ("S2", "S1"), ("S3", "S2"), ("S4", "S3"), ("S5", "S4"), ("S6", "S5"),
                 ("W6", "S4"), ("S4", "S0R"), ("S5", "S0R"), ("S4", "W1"), ("S5", "W1"), ("W5", "S5"), ("W1", "S0R")]
        save("pairs.json", {f"{a}-{b}": {m: ci(rs[a][m] - rs[b][m]) for m in
             ("peak_mean", "peak_lost", "worst_route", "PM_GATE_mean", "PM_mean", "AM_mean", "km")} for a, b in pairs})
        print("scenarios", round(time.time() - t0), "s", flush=True)

        # 3. sensitivity to the assumed inputs, and disruption
        s4, s5 = P(**full, **a), P(**full, **c)
        ch = {
            "Nominal": B,
            "Demand -20%": replace(B, demand_scale=.8), "Demand +20%": replace(B, demand_scale=1.2),
            "Patience 30 min": replace(B, patience_mean=30.), "Patience 90 min": replace(B, patience_mean=90.),
            "Peak congestion x1.0": replace(B, congestion=1.0), "Peak congestion x1.6": replace(B, congestion=1.6),
            "Gate share 15%": replace(B, gate_share=.15), "Gate share 45%": replace(B, gate_share=.45),
            "Boarding 1.5 s": replace(B, board_s=1.5), "Boarding 3.5 s": replace(B, board_s=3.5),
            "Crush limit 65": replace(B, crush=65),
            "Incidents 15% of trips": replace(B, p_incident=.15),
            "4 buses off the road": replace(B, alloc=(9, 8, 6, 3)),
            "Route imbalance cv 0.35": replace(B, route_cv=.35),
        }
        jobs = {}
        for k, v in ch.items():
            jobs[k + "|S0"] = (v, C.S0); jobs[k + "|S0R"] = (v, P(retimed=True))
            jobs[k + "|S4"] = (v, s4); jobs[k + "|S5"] = (v, s5)
        r = run_all(ex, jobs, sens_seeds)
        save("sensitivity.json", {k: {m: ci(v[m]) for m in
             ("peak_mean", "peak_lost", "overcrowd", "worst_route")} |
             {"d": ci(v["peak_mean"] - r[k.split("|")[0] + "|S0"]["peak_mean"]),
              "dR": ci(v["peak_mean"] - r[k.split("|")[0] + "|S0R"]["peak_mean"])} for k, v in r.items()})
        print("sensitivity", round(time.time() - t0), "s", flush=True)

        # 4. quality of the queue counts fed to the dispatcher
        jobs = {f"{nz}|{ag}": (B, replace(s4, count_noise=nz, count_age=ag))
                for nz in (0, .2, .5) for ag in (0, 5, 10, 15)}
        r = run_all(ex, jobs, sens_seeds)
        save("information.json", {k: ci(v["peak_mean"]) for k, v in r.items()})

    # 5. one-day queue traces for the plots
    tr = {}
    for name in ("S0", "S4", "S5"):
        qs = []
        for k in range(min(n, 10)):
            d = M.Day(*sc[name], k); d.run(); qs.append(np.array(d.ql))
        tr[name] = np.mean(qs, axis=0).tolist()
    save("traces.json", tr)
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
