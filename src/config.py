"""Model inputs. Every number here is an ASSUMPTION unless a source is named.

Times are minutes after midnight. Replace these values with field counts
(see README, "Calibrating with real data") before using results operationally.
"""
from dataclasses import dataclass

H = 60.0
ROUTES = ["Qasimabad", "Latifabad", "Hyderabad City", "Kotri"]   # areas named by MUET
SHARE = [0.34, 0.28, 0.24, 0.14]          # share of city demand per route
RUN = [22.0, 36.0, 32.0, 16.0]            # mean free-flow run Main Gate <-> city (min)
DIST = [12.0, 20.0, 17.0, 8.0]            # km, Main Gate <-> city
GATE_STC_MIN, GATE_STC_KM = 4.0, 1.5      # campus leg

PEAKS = {"AM": (8 * H, 9 * H), "PM": (14 * H, 15.5 * H)}   # from the assignment brief

# Demand pulses: (centre, sd, weight). Remaining weight is spread uniformly.
IN_PULSES = [(8 * H + 10, 22, .72), (9 * H + 50, 15, .14)]
IN_UNIF = (7 * H, 13 * H)
OUT_PULSES = [(14 * H + 5, 8, .34), (15 * H + 5, 8, .28), (15 * H + 35, 8, .10),
              (12 * H + 30, 15, .08), (16 * H + 35, 10, .08)]
OUT_UNIF = (7.5 * H, 17 * H)
UTIL_WINDOWS = ((450, 570), (840, 960))   # 7:30-9:30 and 14:00-16:00
SHUT_PULSES = [(8 * H + 20, 15, .70)]
SHUT_UNIF = (8 * H, 15 * H)


@dataclass(frozen=True)
class Policy:
    name: str = "S0 Baseline"
    dispatch: str = "static"        # "static" timetable | "adaptive" load-triggered
    retimed: bool = False           # static only: headway_r = cycle_r / buses_r, no platoons
    pooled: bool = False            # True: any bus may serve any route
    gate_quota: bool = False        # True: hold back places at STC for Main Gate
    reposition: bool = False        # True: return empty before the PM peak and wait at STC
    theta: float = 1.15             # departure load trigger, multiple of seats
    hold: float = 10.0              # longest hold at a terminal (min)
    load_cap: int = 78              # most passengers allowed on board
    stagger: float = 0.0            # split each class-release pulse into +/- stagger (min)
    count_noise: float = 0.0        # relative sd of queue-count error
    count_age: float = 0.0          # age of queue counts (min)


@dataclass(frozen=True)
class System:
    alloc: tuple = (10, 9, 7, 4)    # buses per route (30 in total)
    seats: int = 52
    crush: int = 78
    in_demand: float = 3900.0       # city -> campus passengers per day
    out_demand: float = 3900.0      # campus -> city passengers per day
    shuttle_demand: float = 450.0   # Main Gate -> STC passengers per day
    gate_share: float = 0.30        # outbound passengers who wait at Main Gate
    in_gate_alight: float = 0.30    # inbound passengers who get off at Main Gate
    day_cv: float = 0.12            # day-to-day demand variation
    route_cv: float = 0.15          # route-level variation on a given day
    board_s: float = 2.0            # s per boarding (1.6 s no-fare, TCRP RRD 116, + crowding)
    alight_s: float = 1.5
    dead_s: float = 30.0            # door / pull-out time per stop
    tt_cv: float = 0.15
    congestion: float = 1.25        # run-time multiplier in peaks
    p_incident: float = 0.04        # chance a trip meets an incident
    incident_mean: float = 12.0     # mean added delay (min)
    patience_mean: float = 50.0     # mean wait before a passenger gives up
    headway_peak: float = 15.0      # clock-face timetable
    headway_off: float = 30.0
    start: float = 6 * H + 45
    end: float = 18 * H
    demand_scale: float = 1.0


BASE = System()
S0 = Policy()
