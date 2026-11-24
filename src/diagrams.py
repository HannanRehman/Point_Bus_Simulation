"""Conceptual-model diagrams (system layout, state transitions, dispatch flowchart)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "figures")
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 9})
INK, FILL, ACC = "#1f2937", "#eef2f7", "#dbe7f5"


def box(ax, x, y, w, h, text, fc=FILL, rnd=0.12, fs=9):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, fc=fc, ec=INK, lw=.9,
                                boxstyle=f"round,pad=0,rounding_size={rnd}"))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=INK, linespacing=1.1)


def diamond(ax, x, y, w, h, text, fs=8.5):
    ax.add_patch(Polygon([(x - w / 2, y), (x, y + h / 2), (x + w / 2, y), (x, y - h / 2)],
                         fc="#fff7e6", ec=INK, lw=.9))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=INK, linespacing=1.05)


def arrow(ax, pts, text=None, tp=None, fs=8, ha="center", style="-|>"):
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=.9, solid_capstyle="butt")
    ax.annotate("", xy=pts[-1], xytext=pts[-2],
                arrowprops=dict(arrowstyle=style, color=INK, lw=.9, shrinkA=0, shrinkB=0))
    if text:
        ax.text(*tp, text, fontsize=fs, ha=ha, va="center", color=INK, linespacing=1.05)


def canvas(w, h, xl, yl):
    f, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xl); ax.set_ylim(*yl); ax.axis("off")
    f.subplots_adjust(0.01, 0.01, 0.99, 0.99)
    return f, ax


def layout():
    f, ax = canvas(3.5, 2.35, (0, 10), (0, 6.6))
    box(ax, 1.2, 3.3, 1.8, 1.2, "STC\nterminal", ACC)
    box(ax, 4.3, 3.3, 1.8, 1.2, "Main\nGate", ACC)
    for y, t in zip((5.8, 4.15, 2.45, .8), ("Qasimabad\n12 km, 22 min", "Latifabad\n20 km, 36 min",
                                            "Hyderabad City\n17 km, 32 min", "Kotri\n8 km, 16 min")):
        box(ax, 8.6, y, 2.6, 1.15, t, fs=8)
        arrow(ax, [(5.2, 3.3), (7.3, y)], style="<|-|>")
    arrow(ax, [(2.1, 3.3), (3.4, 3.3)], "4 min", (2.75, 3.62), style="<|-|>")
    ax.text(1.2, 2.35, "outbound queues\n(4 routes, 70%)", ha="center", va="center", fontsize=7.5)
    ax.text(4.1, 2.2, "outbound queues\n(4 routes, 30%)\n+ shuttle queue", ha="center", va="center", fontsize=7.5)
    ax.text(2.7, 5.9, "30 buses, 52 seats,\ncrush load 78", ha="center", va="center", fontsize=8, style="italic")
    f.savefig(os.path.join(OUT, "layout.png"), dpi=300); plt.close(f)


def bus_states():
    f, ax = canvas(3.5, 3.5, (0, 10), (0, 10))
    W, HH = 3.0, 1.15
    L, Rr = 2.1, 7.9
    box(ax, L, 9.0, W, HH, "1 Standby\nat STC", ACC, .5)
    box(ax, L, 6.4, W, HH, "2 Loading\nat STC bay", ACC, .5)
    box(ax, L, 3.6, W, HH, "3 Run STC to\nMain Gate", ACC, .5)
    box(ax, L, 1.0, W, HH, "4 Loading at\nMain Gate", ACC, .5)
    box(ax, Rr, 1.0, W, HH, "5 Outbound\nrun to city", ACC, .5)
    box(ax, Rr, 3.6, W, HH, "6 Unload and\nload in city", ACC, .5)
    box(ax, Rr, 6.4, W, HH, "7 Inbound run\nto Main Gate", ACC, .5)
    box(ax, Rr, 9.0, W, HH, "8 Unload Gate,\nthen STC", ACC, .5)
    arrow(ax, [(L, 8.4), (L, 7.0)], "route chosen,\nbay free", (L + .2, 7.7), ha="left")
    arrow(ax, [(L, 5.8), (L, 4.2)], "load trigger or\nhold limit", (L + .2, 5.0), ha="left")
    arrow(ax, [(L, 3.0), (L, 1.6)], "4 min elapsed", (L + .2, 2.3), ha="left")
    arrow(ax, [(3.6, 1.0), (6.4, 1.0)], "dwell ends", (5.0, 1.35))
    arrow(ax, [(Rr, 1.6), (Rr, 3.0)], "run time T", (Rr - .2, 2.3), ha="right")
    arrow(ax, [(Rr, 4.2), (Rr, 5.8)], "trigger, hold\nor short turn", (Rr - .2, 5.0), ha="right")
    arrow(ax, [(Rr, 7.0), (Rr, 8.4)], "run time T", (Rr - .2, 7.7), ha="right")
    arrow(ax, [(6.4, 9.0), (3.6, 9.0)], "all alighted", (5.0, 9.35))
    f.savefig(os.path.join(OUT, "bus_states.png"), dpi=300); plt.close(f)


def pax_states():
    f, ax = canvas(3.5, 1.5, (0, 10), (0, 4.2))
    box(ax, 1.2, 2.9, 2.0, 1.1, "Arrived", ACC, .5)
    box(ax, 5.0, 2.9, 2.0, 1.1, "Waiting", ACC, .5)
    box(ax, 8.7, 2.9, 2.0, 1.1, "On board", ACC, .5)
    box(ax, 8.7, .75, 2.0, 1.1, "Delivered", ACC, .5)
    box(ax, 5.0, .75, 2.0, 1.1, "Gave up", "#fbe9e7", .5)
    arrow(ax, [(2.2, 2.9), (4.0, 2.9)], "joins queue", (3.1, 3.2), fs=7.5)
    arrow(ax, [(6.0, 2.9), (7.7, 2.9)], "space on bus", (6.85, 3.2), fs=7.5)
    arrow(ax, [(5.0, 2.35), (5.0, 1.3)], "patience ends", (4.85, 1.83), fs=7.5, ha="right")
    arrow(ax, [(8.7, 2.35), (8.7, 1.3)], "bus arrives", (8.55, 1.83), fs=7.5, ha="right")
    f.savefig(os.path.join(OUT, "pax_states.png"), dpi=300); plt.close(f)


def flow():
    f, ax = canvas(3.5, 5.6, (0, 10), (0, 16.6))
    x = 4.6
    box(ax, x, 16.0, 3.6, .9, "Bus empties at STC", ACC, .45)
    diamond(ax, x, 14.5, 4.2, 1.45, "Any bay free?")
    box(ax, x, 12.8, 5.4, 1.15, "Read queue counts; compute\npressure P(r) for each free route")
    box(ax, x, 11.1, 5.4, 1.05, "Take bay of route r* = argmax P(r)\nSet load limit = cap - Gate quota", fs=8.5)
    box(ax, x, 9.5, 4.0, .9, "Board from STC queue")
    diamond(ax, x, 7.9, 4.6, 1.45, "Load reaches\ntrigger?")
    diamond(ax, x, 5.9, 4.6, 1.45, "Near empty and\nfar queue long?")
    diamond(ax, x, 3.9, 4.6, 1.45, "Held for\nhold limit?")
    box(ax, x, 1.9, 4.6, .95, "Depart; fill at Main Gate\nup to cap", ACC)
    box(ax, x, .55, 4.6, .8, "Run to city, return", ACC)
    for a, b in ((15.55, 15.23), (13.77, 13.38), (12.22, 11.63), (10.57, 9.95), (9.05, 8.63),
                 (7.17, 6.63), (5.17, 4.63), (3.17, 2.38), (1.42, .95)):
        arrow(ax, [(x, a), (x, b)])
    ax.text(x + .15, 13.6, "yes", fontsize=8); ax.text(x + .15, 6.82, "no", fontsize=8)
    ax.text(x + .15, 4.82, "no", fontsize=8); ax.text(x + .15, 2.7, "yes", fontsize=8)
    arrow(ax, [(x + 2.1, 14.5), (8.9, 14.5), (8.9, 15.4), (x, 15.4)], "no: stand by\n0.5 min", (7.9, 13.95))
    arrow(ax, [(x + 2.3, 7.9), (9.2, 7.9), (9.2, 1.9), (x + 2.3, 1.9)], "yes", (7.3, 8.15))
    arrow(ax, [(x + 2.3, 5.9), (9.2, 5.9)], "yes, 1 min hold", (8.05, 6.2), style="-")
    arrow(ax, [(x - 2.3, 3.9), (.6, 3.9), (.6, 9.5), (x - 2.0, 9.5)], "no: wait\n0.5 min", (1.35, 4.45))
    f.savefig(os.path.join(OUT, "flowchart.png"), dpi=300); plt.close(f)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    layout(); bus_states(); pax_states(); flow()
