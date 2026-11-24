# MUET Point bus simulation

A discrete-event simulation of the MUET Point bus system, written in Python with SimPy. It compares the current static timetable with load-triggered, pooled dispatching, using the same 30 buses.

Course: Simulation & Modelling, 22SW, 8th semester. Assignment type: Problem Based Learning.

> **About the data.** MUET does not publish its Point timetable, route-wise fleet or passenger counts, so the demand, run-time and fleet numbers in `src/config.py` are assumptions. The four corridors, the two terminals and the peak hours come from the MUET website and the assignment brief. Put field counts into `src/config.py` before using any result to run real buses.

## What is in the folder

| Path | Contents |
|---|---|
| `src/config.py` | Every input: routes, demand, run times, fleet, policy settings |
| `src/model.py` | The SimPy model: passengers, buses, dispatch rules, output statistics |
| `src/validate.py` | Checks against Erlang C, random-headway and bulk-service theory, Little's law and passenger conservation |
| `src/experiments.py` | Tuning grid, scenarios, sensitivity, queue-count quality |
| `src/plots.py`, `src/diagrams.py` | Result figures and conceptual diagrams |
| `results/` | JSON output of the runs |
| `figures/` | PNG figures used in the report |

## Run it

Python 3.10 or newer.

```bash
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Linux / macOS
pip install -r requirements.txt

cd src
python validate.py               # a few minutes
python experiments.py --quick    # smoke test, a few minutes (overwrites results/)
python experiments.py            # full study, 30 replications, about 20 to 30 minutes on 8 cores
python extra.py                  # S5 without pooling, about 1 minute
python plots.py
python diagrams.py
```

Run one day of one policy from a Python shell in `src/`:

```python
import config as C, model as M
base = M.simulate(C.BASE, C.S0, seed=1)
best = M.simulate(C.BASE, C.Policy(dispatch="adaptive", pooled=True, gate_quota=True,
                                   reposition=True, theta=1.25, hold=15, load_cap=65), seed=1)
print(base["peak_mean"], best["peak_mean"])
```

Seeds make every run repeatable. Tuning uses seeds from 1000, evaluation uses 0 to 29 and sensitivity uses seeds from 2000, so no policy is tested on the days that tuned it.

## Scenarios

| Code | Policy |
|---|---|
| S0 | Static clock-face timetable, buses fixed to routes |
| S0R | Static timetable re-timed to each route's cycle and fleet |
| S1 | Load-triggered departure with a hold limit |
| S2 | S1 + Main Gate quota |
| S3 | S2 + pooled fleet (pressure-based route choice) |
| S4 | S3 + pre-peak repositioning |
| S5 | S4 with a 65-passenger load limit |
| S6 | S5 + class release staggered by 15 minutes |
| W1 | S0R with 4 extra buses |
| W2, W3, W4 | S0 with only the Gate quota, only staggering, or only the load limit |
| W5 | S5 with 4 extra buses |
| W6 | S4 + staggering |

## Calibrating with real data

1. Count arrivals per 5 minutes at STC, Main Gate and each city pickup point on at least five working days. Replace the `*_PULSES` lists and the daily totals.
2. Log departure time, arrival time and load for every Point trip on those days. Replace `RUN`, `congestion`, `tt_cv`, `p_incident`, `incident_mean`.
3. Time boarding for 20 or more full buses. Replace `board_s`.
4. Get the real allocation and timetable from the Transport Section. Replace `alloc`, `headway_peak`, `headway_off`.
5. Run S0 and compare simulated waits with observed waits before trusting the other scenarios.
