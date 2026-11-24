"""Checks of the simulation engine against closed-form and numerical results."""
import json, math, os
import numpy as np
import simpy
import config as C
import model as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")


def mmc(lam, mu, c, n=200000, reps=12):
    """M/M/c mean queue wait: Erlang C against SimPy, averaged over seeds."""
    a = lam / mu
    pc = a ** c / math.factorial(c) * c / (c - a)
    p0 = sum(a ** k / math.factorial(k) for k in range(c)) + pc
    exact = (pc / p0) / (c * mu - lam)
    means = []
    for seed in range(reps):
        g, env, w = np.random.default_rng(seed), simpy.Environment(), []
        srv = simpy.Resource(env, c)

        def cust():
            t = env.now
            with srv.request() as q:
                yield q
                w.append(env.now - t)
                yield env.timeout(g.exponential(1 / mu))

        def src():
            for _ in range(n):
                yield env.timeout(g.exponential(1 / lam))
                env.process(cust())
        env.process(src())
        env.run()
        means.append(np.mean(w[2000:]))
    return exact, float(np.mean(means)), float(np.std(means, ddof=1) / np.sqrt(reps))


def random_headway(lam, mean_h, cv, horizon=400000, seed=2):
    """Uncapacitated stop, gamma headways: W = E[H](1 + cv^2)/2."""
    exact = mean_h * (1 + cv * cv) / 2
    g, env, q, w = np.random.default_rng(seed), simpy.Environment(), [], []

    def pax():
        while True:
            yield env.timeout(g.exponential(1 / lam))
            q.append(env.now)

    def bus():
        k = 1 / cv ** 2
        while True:
            yield env.timeout(g.gamma(k, mean_h / k))
            w.extend(env.now - t for t in q)
            q.clear()
    env.process(pax()); env.process(bus())
    env.run(until=horizon)
    return exact, float(np.mean(w))


def bulk(lam, H, K, horizon=1500000, seed=3):
    """Fixed headway H, capacity K. Embedded chain Q' = max(Q - K, 0) + A."""
    N, m = 40 * K, lam * H
    pa = np.exp([-m + k * math.log(m) - math.lgamma(k + 1) for k in range(N)])
    pi = np.zeros(N); pi[0] = 1.0                      # queue just before a departure
    for _ in range(6000):
        left = np.zeros(N)
        left[0] = pi[:K + 1].sum()
        left[1:N - K] = pi[K + 1:]
        new = np.convolve(left, pa)[:N]
        new /= new.sum()
        if np.abs(new - pi).sum() < 1e-12:
            break
        pi = new
    left_mean = sum(max(q - K, 0) * p for q, p in enumerate(pi))
    exact = (left_mean + m / 2) / lam                  # Little: Lq = E[left] + lam H / 2
    g, env, q, w = np.random.default_rng(seed), simpy.Environment(), [], []

    def pax():
        while True:
            yield env.timeout(g.exponential(1 / lam))
            q.append(env.now)

    def bus():
        while True:
            yield env.timeout(H)
            w.extend(env.now - t for t in q[:K])
            del q[:K]
    env.process(pax()); env.process(bus())
    env.run(until=horizon)
    return exact, float(np.mean(w[5000:]))


def little(seed=7, dt=0.1):
    """Little's law on the full model: integral of queue length = total queueing time.
    Sampled off the event grid so boardings on whole minutes are not double counted."""
    d = M.Day(C.BASE, C.S0, seed)
    area = [0.0]

    def probe():
        yield d.env.timeout(0.037)
        while True:
            c = d.counts()
            area[0] += dt * (sum(sum(v) for v in c.values()) + d.purge(d.q_shut))
            yield d.env.timeout(dt)
    d.env.process(probe())
    d.run()
    return float(sum(p.queue_time for p in d.pax)), area[0]


def conservation(n=40):
    bad, gen, exp = 0, [], []
    for k in range(n):
        d = M.Day(C.BASE, C.S0, k)
        d.run()
        b = sum(p.board is not None for p in d.pax)
        carried = sum(t[3] for t in d.trips)
        lost = sum(p.board is None for p in d.pax)
        bad += (b + lost != len(d.pax))
        tr_out = sum(t[3] for t in d.trips if t[2] == "OUT")
        tr_in = sum(t[3] for t in d.trips if t[2] == "IN")
        rode_out = sum(p.board is not None and p.dest == "CITY" for p in d.pax)
        rode_in = sum(p.board is not None and p.stop == "CITY" for p in d.pax)
        bad += (tr_out != rode_out) + (tr_in != rode_in)
        gen.append(len(d.pax) / d.day_f); exp.append(8250.0)
    return bad, float(np.mean(gen)), 8250.0


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    r = {"M/M/3 wait (lam=2.5, mu=1)": mmc(2.5, 1, 3),
         "Random headway (H=10, cv=0.5)": random_headway(3, 10, .5),
         "Bulk service (lam=4.6, H=15, K=78)": bulk(4.6, 15, 78),
         "Little's law (passenger-min)": little()}
    for k, (a, b, *_) in r.items():
        print(f"{k:40s} reference={a:10.3f} simulation={b:10.3f} error={100*(b-a)/a:+.2f}%")
    c = conservation()
    print("conservation violations:", c[0], "| mean arrivals / day factor:", round(c[1], 1), "expected", c[2])
    json.dump({"tests": r, "conservation": c}, open(os.path.join(OUT, "validation.json"), "w"), indent=1)
