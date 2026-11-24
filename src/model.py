"""Discrete-event model of the MUET Point bus system (SimPy).

Entities   passengers, buses
Resources  one loading bay per route at each terminal
Queues     OUT[stop][route] for stop in STC, GATE; IN[route] at the city end;
           SHUT at Main Gate for the short hop to STC
Run        one day per replication (terminating simulation)
"""
import math
from collections import deque
import numpy as np
import simpy
import config as C
from config import ROUTES, RUN, DIST, SHARE, PEAKS

R = range(len(ROUTES))
STOPS = ("STC", "GATE", "CITY")


class Pax:
    __slots__ = ("t", "deadline", "stop", "route", "dest", "board", "left")

    def __init__(self, t, patience, stop, route, dest):
        self.t, self.deadline = t, t + patience
        self.stop, self.route, self.dest = stop, route, dest
        self.board = None                       # boarding time; None if never boarded
        self.left = None                        # time the bus left this passenger's stop

    @property
    def queue_time(self):
        return (self.deadline if self.board is None else self.board) - self.t

    @property
    def wait(self):
        """Arrival at the stop until the bus LEAVES it, so sitting on a held bus counts."""
        if self.board is None:
            return self.deadline - self.t
        return (self.board if self.left is None else self.left) - self.t


def pulse_rate(t, pulses, unif, stagger=0.0):
    """Arrival density (1/min) of a pulse mixture; integrates to about 1."""
    f, w = 0.0, 0.0
    for c, sd, wt in pulses:
        w += wt
        centres = (c,) if stagger == 0 else (c - stagger, c, c + stagger)
        for cc in centres:
            z = (t - cc) / sd
            f += wt / len(centres) * math.exp(-.5 * z * z) / (sd * 2.5066283)
    a, b = unif
    if a <= t < b:
        f += (1 - w) / (b - a)
    return f


class Day:
    def __init__(self, sysc, pol, seed):
        self.s, self.p = sysc, pol
        names = ["day", "in", "out", "shut", "tt0", "tt1", "tt2", "tt3", "noise"]
        kids = np.random.SeedSequence(seed).spawn(len(names))   # one stream per source
        self.rng = {k: np.random.default_rng(x) for k, x in zip(names, kids)}
        self.env = simpy.Environment(initial_time=sysc.start)
        self.q_out = {st: [deque() for _ in R] for st in ("STC", "GATE")}
        self.q_in = [deque() for _ in R]
        self.q_shut = deque()
        self.pax, self.trips = [], []
        self.bay = {(st, r): simpy.Resource(self.env, 1) for st in ("STC", "CITY") for r in R}
        self.enroute_in, self.enroute_out = [0] * 4, [0] * 4
        self.next_dep = {}
        self.busy = {"moving": 0.0, "dwell": 0.0, "peak": 0.0}
        self.snap = deque()                     # (time, counts) for delayed information
        self.ql = []                            # queue-length trace
        g = self.rng["day"]
        self.day_f = sysc.demand_scale * g.lognormal(-sysc.day_cv ** 2 / 2, sysc.day_cv)
        rf = g.lognormal(-sysc.route_cv ** 2 / 2, sysc.route_cv, 4) * np.array(SHARE)
        self.share = rf / rf.sum()

    # ---------- arrivals: non-homogeneous Poisson by thinning ----------
    def arrivals(self, key, total, pulses, unif, make, stagger=0.0):
        g, env = self.rng[key], self.env
        grid = np.arange(self.s.start, self.s.end, 1.0)
        lam = total * self.day_f
        peak = lam * max(pulse_rate(t, pulses, unif, stagger) for t in grid) * 1.02
        while True:
            yield env.timeout(g.exponential(1 / peak))
            u, v, w, pt = g.random(4)
            if env.now >= self.s.end - 30:
                return
            if u * peak <= lam * pulse_rate(env.now, pulses, unif, stagger):
                # Weibull(k=2.5) patience; 0.8873 = Gamma(1 + 1/2.5)
                patience = self.s.patience_mean / 0.8873 * (-math.log(1 - pt)) ** (1 / 2.5)
                make(env.now, patience, v, w)

    def _route(self, v):
        c = 0.0
        for r in R:
            c += self.share[r]
            if v < c:
                return r
        return 3

    def make_out(self, t, pat, v, w):
        r, st = self._route(v), "GATE" if w < self.s.gate_share else "STC"
        p = Pax(t, pat, st, r, "CITY")
        self.q_out[st][r].append(p)
        self.pax.append(p)

    def make_in(self, t, pat, v, w):
        r = self._route(v)
        p = Pax(t, pat, "CITY", r, "GATE" if w < self.s.in_gate_alight else "STC")
        self.q_in[r].append(p)
        self.pax.append(p)

    def make_shut(self, t, pat, v, w):
        p = Pax(t, pat, "GATE", -1, "STC")
        self.q_shut.append(p)
        self.pax.append(p)

    # ---------- queues ----------
    def purge(self, q):
        """Remove passengers whose patience has run out; return live length."""
        now = self.env.now
        if any(p.deadline <= now for p in q):
            keep = [p for p in q if p.deadline > now]
            q.clear()
            q.extend(keep)
        return len(q)

    def counts(self):
        return dict(stc=[self.purge(self.q_out["STC"][r]) for r in R],
                    gate=[self.purge(self.q_out["GATE"][r]) for r in R],
                    city=[self.purge(self.q_in[r]) for r in R])

    def observed(self):
        """Counts as the dispatcher sees them: possibly old, possibly wrong."""
        c = self.counts()
        if self.p.count_age > 0:
            t = self.env.now - self.p.count_age
            old = [x for x in self.snap if x[0] <= t]
            c = old[-1][1] if old else c
        if self.p.count_noise > 0:
            g = self.rng["noise"]
            c = {k: [max(0, round(x * g.normal(1, self.p.count_noise))) for x in v]
                 for k, v in c.items()}
        return c

    def board(self, q, onboard, limit):
        """Load from q until limit; returns number boarded (caller charges the time)."""
        n = 0
        self.purge(q)
        while q and len(onboard) < limit:
            p = q.popleft()
            p.board = self.env.now
            onboard.append(p)
            n += 1
        return n

    def depart(self, onboard):
        for p in onboard:
            if p.left is None:
                p.left = self.env.now

    # ---------- travel ----------
    def cong(self):
        t = self.env.now
        return self.s.congestion if (450 <= t < 540 or 840 <= t < 930) else 1.0

    def run_time(self, r):
        g, cv = self.rng[f"tt{r}"], self.s.tt_cv
        sig = math.sqrt(math.log(1 + cv * cv))
        x = RUN[r] * self.cong() * g.lognormal(-sig * sig / 2, sig)
        u, e = g.random(), g.exponential(self.s.incident_mean)
        return x + (e if u < self.s.p_incident else 0.0)

    def log_peak(self, t):
        a, b = self.env.now, self.env.now + t
        self.busy["peak"] += sum(max(0.0, min(b, y) - max(a, x)) for x, y in C.UTIL_WINDOWS)

    def move(self, t):
        self.busy["moving"] += t
        self.log_peak(t)
        return self.env.timeout(t)

    def dwell(self, n_on, n_off):
        t = (self.s.dead_s + n_on * self.s.board_s + n_off * self.s.alight_s) / 60
        self.busy["dwell"] += t
        self.log_peak(t)
        return self.env.timeout(t)

    # ---------- dispatch rules ----------
    def cycle(self, r):
        """Scheduled peak round trip of one bus on route r (min)."""
        return 2 * (RUN[r] * self.s.congestion + C.GATE_STC_MIN) + 8

    def is_peak(self):
        return 450 <= self.env.now < 570 or 810 <= self.env.now < 960

    def headway(self, r=None):
        if r is not None and self.p.retimed and self.is_peak():
            return self.cycle(r) / self.s.alloc[r]
        return self.s.headway_peak if self.is_peak() else self.s.headway_off

    def platoon(self, r):
        """Buses per timetable slot that the route's allocation can sustain."""
        if self.p.retimed:
            return 1
        return max(1, int(self.s.alloc[r] * self.s.headway_peak / self.cycle(r)))

    def scheduled(self, st, r):
        """Timetable slot for this bus. A bus up to `grace` minutes late still runs
        the slot it missed if that slot has an unused departure; otherwise it
        takes the next slot that has one."""
        now, h = self.env.now, self.headway(r)
        used = self.next_dep.setdefault((st, r), {})
        cap, grace = self.platoon(r), min(5.0, h / 2)
        k = math.ceil(now / h - 1e-9)
        if now - (k - 1) * h > grace or used.get(round((k - 1) * h, 3), 0) >= cap:
            while used.get(round(k * h, 3), 0) >= cap:
                k += 1
        else:
            k -= 1
        key = round(k * h, 3)
        used[key] = used.get(key, 0) + 1
        return k * h

    def pressure(self, r, c):
        """Unmet passengers on route r per minute of bus cycle (both directions)."""
        T = RUN[r] * self.cong() + C.GATE_STC_MIN
        out = c["stc"][r] + c["gate"][r]
        rate = (self.s.in_demand * SHARE[r] *
                pulse_rate(self.env.now + T, C.IN_PULSES, C.IN_UNIF))
        inn = max(0.0, c["city"][r] + rate * T - self.s.seats * self.enroute_out[r])
        return (out + inn) / (2 * T + 6)

    def choose_route(self):
        """Pooled fleet: free bay with the highest pressure; None means stand by."""
        c = self.observed()
        free = [r for r in R if self.bay[("STC", r)].count == 0]
        if not free:
            return None
        return max(free, key=lambda r: self.pressure(r, c))

    def load_and_wait(self, st, r, onboard):
        """Hold at a terminal, load continuously, leave by the active rule."""
        env, pol, s = self.env, self.p, self.s
        q = self.q_out["STC"][r] if st == "STC" else self.q_in[r]
        arrive = env.now
        cap = min(pol.load_cap, s.crush)
        dep = self.scheduled(st, r) if pol.dispatch == "static" else None
        while True:
            limit = cap
            if st == "STC" and pol.gate_quota:
                waiting = self.observed()["gate"][r]
                limit = cap - min(waiting, int(round(cap * s.gate_share)))
            n = self.board(q, onboard, limit)
            if n:
                yield self.dwell(n, 0)
            now = env.now
            if pol.dispatch == "static":
                if now >= dep:
                    return
                yield env.timeout(min(0.5, max(dep - now, .01)))
                continue
            if len(onboard) >= min(int(pol.theta * s.seats), limit):
                return                                          # load trigger
            o = self.observed()
            far = o["city"][r] if st == "STC" else o["stc"][r] + o["gate"][r]
            urgent = len(onboard) < 0.3 * s.seats and far > s.seats
            hold = pol.hold
            if not self.is_peak():
                hold = max(hold, s.headway_off)                 # same off-peak service as S0
            if pol.reposition and st == "CITY" and 790 <= now < 950:
                hold = 2.0                                      # 13:10-15:50: come back for PM
            if pol.reposition and st == "STC" and 800 <= now < 840:
                hold = max(hold, 840 - arrive)                  # 13:20-14:00: wait for release
            if urgent:
                hold = 1.0                                      # short turn to the long queue
            if now - arrive >= hold:
                return
            yield env.timeout(0.5)

    # ---------- bus life cycle ----------
    def bus(self, i, home):
        env, s, p = self.env, self.s, self.p
        r, at = home, "CITY"
        yield env.timeout((i % 10) * 1.5)
        while env.now < s.end:
            onboard = []
            if at == "STC":
                if p.pooled:
                    r = self.choose_route()
                    while r is None:
                        yield env.timeout(0.5)
                        r = self.choose_route()
                with self.bay[("STC", r)].request() as bay:
                    yield bay
                    if env.now >= s.end:
                        return
                    yield from self.load_and_wait("STC", r, onboard)
                self.depart(onboard)
                self.enroute_out[r] += 1
                t0, n_stc = env.now, len(onboard)
                yield self.move(C.GATE_STC_MIN)
                n = self.board(self.q_out["GATE"][r], onboard, min(p.load_cap, s.crush))
                yield self.dwell(n, 0)
                self.depart(onboard)
                rt = self.run_time(r)
                yield self.move(rt)
                yield self.dwell(0, len(onboard))
                self.enroute_out[r] -= 1
                self.trips.append((t0, r, "OUT", len(onboard), rt, n_stc))
                at = "CITY"
            else:
                with self.bay[("CITY", r)].request() as bay:
                    yield bay
                    if env.now >= s.end:
                        return
                    yield from self.load_and_wait("CITY", r, onboard)
                self.depart(onboard)
                self.enroute_in[r] += 1
                t0, n0 = env.now, len(onboard)
                rt = self.run_time(r)
                yield self.move(rt)
                off = [x for x in onboard if x.dest == "GATE"]
                onboard = [x for x in onboard if x.dest != "GATE"]
                n = self.board(self.q_shut, onboard, min(p.load_cap, s.crush))
                yield self.dwell(n, len(off))
                self.depart(onboard)
                yield self.move(C.GATE_STC_MIN)
                yield self.dwell(0, len(onboard))
                self.enroute_in[r] -= 1
                self.trips.append((t0, r, "IN", n0, rt, n0))
                at = "STC"

    def monitor(self):
        while True:
            c = self.counts()
            self.snap.append((self.env.now, c))
            if len(self.snap) > 60:
                self.snap.popleft()
            self.ql.append((self.env.now, sum(c["stc"]),
                            sum(c["gate"]) + self.purge(self.q_shut), sum(c["city"])))
            yield self.env.timeout(1.0)

    def run(self):
        s, e = self.s, self.env
        e.process(self.monitor())
        e.process(self.arrivals("in", s.in_demand, C.IN_PULSES, C.IN_UNIF, self.make_in))
        e.process(self.arrivals("out", s.out_demand, C.OUT_PULSES, C.OUT_UNIF,
                                self.make_out, self.p.stagger))
        e.process(self.arrivals("shut", s.shuttle_demand, C.SHUT_PULSES, C.SHUT_UNIF,
                                self.make_shut))
        i = 0
        for r, n in enumerate(s.alloc):
            for _ in range(n):
                e.process(self.bus(i, r))
                i += 1
        e.run(until=s.end + 90)
        return self.metrics()

    # ---------- output statistics ----------
    def metrics(self):
        m, s = {}, self.s
        end = s.end + 90
        for p in self.pax:                       # still queued at close: cut at closing time
            if p.board is None:
                p.deadline = min(p.deadline, end)

        def stats(tag, ps):
            w = np.array([p.wait for p in ps]) if ps else np.zeros(1)
            m[f"{tag}_mean"] = w.mean()
            m[f"{tag}_p95"] = np.percentile(w, 95)
            m[f"{tag}_gt20"] = 100 * (w > 20).mean()
            m[f"{tag}_lost"] = 100 * np.mean([p.board is None for p in ps]) if ps else 0.0

        def inpk(p, k):
            return PEAKS[k][0] <= p.t < PEAKS[k][1]

        pk = [p for p in self.pax if inpk(p, "AM") or inpk(p, "PM")]
        stats("all", self.pax)
        stats("peak", pk)
        for k in PEAKS:
            stats(k, [p for p in pk if inpk(p, k)])
            for st in STOPS:
                stats(f"{k}_{st}", [p for p in pk if inpk(p, k) and p.stop == st])
        for r in R:
            stats(f"r{r}", [p for p in pk if p.route == r])
        m["worst_route"] = max(m[f"r{r}_mean"] for r in R)
        ql = np.array(self.ql)
        m["qmax_STC"], m["qmax_GATE"] = ql[:, 1].max(), ql[:, 2].max()
        ptr = [t for t in self.trips if any(a <= t[0] < b for a, b in PEAKS.values())]
        load = np.array([t[3] for t in self.trips])
        carried = load.sum()
        m["overcrowd"] = 100 * load[load > 1.25 * s.seats].sum() / max(1, carried)
        m["gt_seats"] = 100 * load[load > s.seats].sum() / max(1, carried)
        m["trips"] = len(load)
        m["km"] = sum(DIST[t[1]] + C.GATE_STC_KM for t in self.trips)
        m["peak_trips"] = len(ptr)
        pd = [t for t in ptr if (t[2] == "IN") == (t[0] < 720)]
        m["peakdir_load"] = 100 * np.mean([t[3] for t in pd]) / s.seats if pd else 0
        m["empty_km"] = 100 * sum(DIST[t[1]] + 1.5 for t in self.trips if t[3] < 5) / m["km"]
        avail = sum(s.alloc) * (s.end - s.start)
        m["util_time"] = 100 * (self.busy["moving"] + self.busy["dwell"]) / avail
        m["util_peak"] = 100 * self.busy["peak"] / (sum(s.alloc) * 240)
        m["carried"] = sum(p.board is not None for p in self.pax)
        m["pax_per_km"] = m["carried"] / m["km"]
        m["generated"] = len(self.pax)
        return m


def simulate(sysc, pol, seed):
    return Day(sysc, pol, seed).run()
