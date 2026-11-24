"""Builds every result figure from results/*.json."""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import config as C
import model as M

HERE = os.path.dirname(os.path.abspath(__file__))
RES, OUT = os.path.join(HERE, "..", "results"), os.path.join(HERE, "..", "figures")
BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8.5, "axes.edgecolor": "#c3c2b7",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.color": GRID, "grid.linewidth": .6, "axes.axisbelow": True,
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "legend.frameon": False,
                     "axes.labelcolor": INK, "lines.linewidth": 1.6})


def L(n):
    return json.load(open(os.path.join(RES, n)))


def save(f, n):
    f.tight_layout(pad=.4)
    f.savefig(os.path.join(OUT, n + ".png"), dpi=300, bbox_inches="tight", pad_inches=.03)
    plt.close(f)


def hours(ax, a=7, b=18, step=2):
    ax.set_xlim(a * 60, b * 60)
    ax.set_xticks(range(a * 60, b * 60 + 1, step * 60), [f"{h}:00" for h in range(a, b + 1, step)])
    for x, y in C.PEAKS.values():
        ax.axvspan(x, y, color="#f0efec", zorder=0, lw=0)


def demand():
    t = np.arange(6.75 * 60, 18 * 60)
    f, ax = plt.subplots(figsize=(3.45, 2.1))
    s = C.BASE
    for tot, p, u, col, lab in ((s.in_demand, C.IN_PULSES, C.IN_UNIF, BLUE, "City to campus"),
                                (s.out_demand, C.OUT_PULSES, C.OUT_UNIF, ORANGE, "Campus to city"),
                                (s.shuttle_demand, C.SHUT_PULSES, C.SHUT_UNIF, AQUA, "Gate to STC shuttle")):
        ax.plot(t, [tot * M.pulse_rate(x, p, u) for x in t], color=col, label=lab)
    hours(ax)
    ax.set_ylabel("Passengers per minute")
    ax.set_ylim(0)
    ax.legend(loc="lower center", bbox_to_anchor=(.48, 1.0), ncol=3, fontsize=7.2, handlelength=1.2, columnspacing=1)
    save(f, "demand")


def traces():
    tr = L("traces.json")
    f, axs = plt.subplots(3, 1, figsize=(3.45, 4.2), sharex=True)
    for ax, i, nm in zip(axs, (3, 1, 2), ("City stops", "STC", "Main Gate")):
        for k, col, lab in (("S0", ORANGE, "S0 baseline"), ("S4", BLUE, "S4 full adaptive"),
                            ("S5", AQUA, "S5 adaptive, 65 limit")):
            a = np.array(tr[k])
            ax.plot(a[:, 0], a[:, i], color=col, label=lab, lw=1.4)
        hours(ax)
        ax.set_ylim(0)
        ax.set_title(nm, fontsize=8.5, loc="left", pad=2)
        ax.set_ylabel("Waiting")
    axs[0].legend(fontsize=7.5, loc="upper right")
    save(f, "traces")


def scenarios():
    s = L("scenarios.json")
    ks = ["S0", "S0R", "S1", "S2", "S3", "S4", "S5", "S6"]
    nm = ["S0 Baseline", "S0R Re-timed", "S1 Load trigger", "S2 + Gate quota", "S3 + Pooled fleet",
          "S4 + Reposition", "S5 S4, 65 limit", "S6 S5 + stagger"]
    f, axs = plt.subplots(1, 3, figsize=(7.1, 2.35), sharey=True)
    for ax, m, t in zip(axs, ("peak_mean", "peak_lost", "overcrowd"),
                        ("Mean peak wait (min)", "Peak passengers lost (%)", "Riders on buses over 65 (%)")):
        v = np.array([s[k][m] for k in ks])
        y = np.arange(len(ks))[::-1]
        ax.barh(y, v[:, 0], xerr=v[:, 1], height=.62, color=[MUTED, MUTED] + [BLUE] * 6,
                error_kw=dict(lw=.8, capsize=1.5, ecolor=INK))
        for yy, (x, e) in zip(y, v):
            ax.text(x + e + v[:, 0].max() * .02, yy, f"{x:.1f}", va="center", fontsize=7.5)
        ax.set_yticks(y, nm)
        ax.set_title(t, fontsize=8.5, loc="left", pad=3)
        ax.set_xlim(0, v[:, 0].max() * 1.2)
        ax.grid(axis="y", visible=False)
        ax.tick_params(length=0)
    save(f, "scenarios")


def stops():
    s = L("scenarios.json")
    cats = [("AM_CITY", "AM\nCity"), ("AM_GATE", "AM\nGate"), ("AM_STC", "AM\nSTC"),
            ("PM_STC", "PM\nSTC"), ("PM_GATE", "PM\nGate")]
    f, ax = plt.subplots(figsize=(3.45, 2.2))
    x = np.arange(len(cats))
    for j, (k, col, lab) in enumerate((("S0", ORANGE, "S0 baseline"), ("S4", BLUE, "S4"), ("S5", AQUA, "S5"))):
        v = np.array([s[k][c + "_mean"] for c, _ in cats])
        ax.bar(x + (j - 1) * .27, v[:, 0], .25, yerr=v[:, 1], color=col, label=lab,
               error_kw=dict(lw=.7, capsize=1.2))
    ax.set_xticks(x, [c[1] for c in cats])
    ax.set_ylabel("Mean wait (min)")
    ax.grid(axis="x", visible=False)
    ax.legend(fontsize=7.5, loc="upper center")
    ax.tick_params(axis="x", length=0)
    save(f, "stops")


def grid():
    g, best = L("grid.json"), L("best.json")
    ths = sorted({float(k.split("|")[1]) for k in g})
    hs = sorted({int(k.split("|")[2]) for k in g})
    f, axs = plt.subplots(2, 1, figsize=(3.45, 3.7))
    vals = [v["peak_mean"] for v in g.values()]
    mid = (min(vals) + max(vals)) / 2
    cm = matplotlib.colors.LinearSegmentedColormap.from_list("b", ["#cde2fb", "#3987e5", "#0d366b"])
    for ax, cap in zip(axs, ("65", "78")):
        tt = [t for t in ths if f"{cap}|{t}|{hs[0]}" in g]
        z = np.array([[g[f"{cap}|{t}|{h}"]["peak_mean"] for h in hs] for t in tt])
        ax.imshow(z, cmap=cm, vmin=min(vals), vmax=max(vals), aspect="auto", origin="lower")
        for i in range(len(tt)):
            for j in range(len(hs)):
                b = [tt[i], float(hs[j])] == best[cap]
                ax.text(j, i, f"{z[i, j]:.1f}", ha="center", va="center", fontsize=8,
                        fontweight="bold" if b else "normal", color="white" if z[i, j] > mid - 1 else INK)
                if b:
                    ax.add_patch(plt.Rectangle((j - .47, i - .46), .94, .92, fill=False, ec=ORANGE, lw=2))
        ax.set_xticks(range(len(hs)), hs)
        ax.set_yticks(range(len(tt)), tt)
        ax.grid(False)
        ax.set_ylabel("Load trigger (x seats)")
        ax.set_title(f"Load limit {cap}: mean peak wait (min)", fontsize=8.5, loc="left", pad=2)
        ax.spines[:].set_visible(False)
        ax.tick_params(length=0)
    axs[1].set_xlabel("Hold limit (min)")
    save(f, "grid")


def pareto():
    g, s = L("grid.json"), L("scenarios.json")
    f, ax = plt.subplots(figsize=(3.45, 2.4))
    ax.scatter([v["overcrowd"] for v in g.values()], [v["peak_mean"] for v in g.values()],
               s=14, color=MUTED, label="Tuning grid", lw=0)
    for k, col, (dx, dy) in (("S0", ORANGE, (6, -3)), ("S0R", ORANGE, (6, -3)), ("W4", ORANGE, (6, -3)),
                             ("S4", BLUE, (6, -3)), ("S5", BLUE, (6, -3))):
        x, y = s[k]["overcrowd"][0], s[k]["peak_mean"][0]
        ax.scatter([x], [y], s=34, color=col, ec="white", lw=.8, zorder=3)
        ax.annotate(k, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=8)
    ax.scatter([], [], s=30, color=ORANGE, label="Static timetable")
    ax.scatter([], [], s=30, color=BLUE, label="Adaptive")
    ax.set_xlabel("Riders on buses over 65 passengers (%)")
    ax.set_ylabel("Mean peak wait (min)")
    ax.legend(fontsize=7.5, loc="upper center")
    ax.set_xlim(-4, 100)
    ax.margins(y=.12)
    save(f, "pareto")


def sensitivity():
    s = L("sensitivity.json")
    ks = [k.split("|")[0] for k in s if k.endswith("|S0")]
    f, ax = plt.subplots(figsize=(3.45, 3.5))
    y = np.arange(len(ks))[::-1]
    for p, col, lab, dy in (("S4", BLUE, "S4 full adaptive", .14), ("S5", AQUA, "S5 adaptive, 65 limit", -.14)):
        v = np.array([s[f"{k}|{p}"]["d"] for k in ks])
        ax.errorbar(v[:, 0], y + dy, xerr=v[:, 1], fmt="o", ms=4, color=col, label=lab, lw=1, capsize=1.5)
    ax.axvline(0, color=INK, lw=.8)
    ax.set_yticks(y, ks, fontsize=7.8)
    ax.set_xlabel("Change in mean peak wait against S0 (min)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.legend(fontsize=7.5, loc="lower center", bbox_to_anchor=(.3, 1.0), ncol=2, columnspacing=1)
    save(f, "sensitivity")


def information():
    s, base = L("information.json"), L("sensitivity.json")["Nominal|S0"]["peak_mean"][0]
    f, ax = plt.subplots(figsize=(3.45, 2.1))
    ag = (0, 5, 10, 15)
    for nz, col, lab in ((0, BLUE, "Exact counts"), (.2, AQUA, "20% count error"), (.5, ORANGE, "50% count error")):
        v = np.array([s[f"{nz}|{a}"] for a in ag])
        ax.plot(ag, v[:, 0], "-o", ms=4, color=col, label=lab)
    ax.axhline(base, color=MUTED, lw=1, ls="--")
    ax.text(15, base + .25, "S0 baseline", ha="right", va="bottom", fontsize=7.5)
    ax.set_xticks(ag)
    ax.set_xlabel("Age of queue counts (min)")
    ax.set_ylabel("Mean peak wait (min)")
    ax.set_ylim(0, base * 1.15)
    ax.legend(fontsize=7.5, loc="lower right")
    save(f, "information")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (demand, traces, scenarios, stops, grid, pareto, sensitivity, information):
        fn()
