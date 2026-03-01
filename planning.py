#!/usr/bin/env python3
"""
10-week constrained randomized sampling schedule with 1-hour sessions.

Goal requested by user:
- Total observation effort = 160 hours, using 1-hour sessions => 160 sessions total
- 10 weeks, 4 observation days/week => 40 observation days total
- Therefore: 4 sessions/day (40*4 = 160 sessions)

Constraints:
- 10 weeks total
- Two conditions: Control and Natural, 5 weeks each
- Week 1 must be Control
- 4 observation days per week, randomly selected
- Week 1: Monday is NOT allowed as an observation day (nests not placed yet)
- Each observation day has 4 sessions of 1 hour within 08:00–17:00
  => start hours are 08..16 (inclusive)
- Within a day, sessions must not overlap => start hours must be distinct

Hour-bin balancing:
- Hour-bins are the 1-hour intervals: 08–09, 09–10, ..., 16–17 (9 bins, start hours 8..16)
- With 160 sessions total, ideal per bin is 160/9 ≈ 17.78
- We balance exactly as evenly as possible: 7 bins get 18 sessions, 2 bins get 17 sessions.
  (Which bins get 18 vs 17 is randomized but reproducible via --seed)

Usage (Windows PowerShell):
  cd $HOME\\Desktop
  python planning.py --start-date 2026-03-02 --seed 18 --out schedule.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple


DAY_NAMES_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass(frozen=True)
class Session:
    week_index: int
    condition: str
    day_date: date
    day_name: str
    session_index: int
    start_hour: int
    start_time: str
    end_time: str


def parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid --start-date '{s}'. Expected YYYY-MM-DD.") from e


def daterange_week(start: date, week_index: int) -> List[date]:
    week_start = start + timedelta(days=(week_index - 1) * 7)
    return [week_start + timedelta(days=i) for i in range(7)]


def choose_conditions(rng: random.Random) -> List[str]:
    # Week 1 fixed as Control; remaining 9 weeks randomized with 4 Control + 5 Natural
    remaining = ["Control"] * 4 + ["Natural"] * 5
    rng.shuffle(remaining)
    return ["Control"] + remaining


def choose_observation_days_for_week(rng: random.Random, week_dates: List[date], week_index: int) -> List[date]:
    # Week 1: exclude Monday
    if week_index == 1:
        allowed = [d for d in week_dates if d.weekday() != 0]
    else:
        allowed = week_dates[:]
    chosen = rng.sample(allowed, 4)
    chosen.sort()
    return chosen


def fmt_time(h: int) -> str:
    return f"{h:02d}:00"


def build_obs_days(start_date: date, seed: int) -> List[Tuple[int, str, date]]:
    rng = random.Random(seed)
    conditions = choose_conditions(rng)

    obs_days: List[Tuple[int, str, date]] = []
    for week_idx in range(1, 11):
        week_dates = daterange_week(start_date, week_idx)
        chosen_days = choose_observation_days_for_week(rng, week_dates, week_idx)
        cond = conditions[week_idx - 1]
        for d in chosen_days:
            obs_days.append((week_idx, cond, d))

    # Stable ordering for readable printing
    obs_days.sort(key=lambda x: (x[0], x[2]))
    return obs_days


def build_balanced_hour_bin_targets(rng: random.Random) -> Dict[int, int]:
    """
    Hour bins correspond to start hours 8..16 inclusive (9 bins).
    Total sessions = 160. Balance as evenly as possible:
      base = 160//9 = 17, remainder = 7
      => 7 bins at 18 and 2 bins at 17.
    """
    bins = list(range(8, 17))  # 8..16
    base = 160 // len(bins)    # 17
    rem = 160 % len(bins)      # 7

    targets = {b: base for b in bins}
    rng.shuffle(bins)
    for b in bins[:rem]:
        targets[b] += 1
    return targets


def weighted_pick_one(rng: random.Random, items: List[int], weights: List[int]) -> int:
    """Weighted choice among items, proportional to weights (all weights > 0)."""
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if acc >= r:
            return it
    return items[-1]


def pick_k_distinct_hours_weighted(rng: random.Random, counts: Dict[int, int], k: int) -> List[int] | None:
    """
    Pick k distinct start hours from those with count>0, weighted by remaining counts.
    Returns None if not enough distinct hours remain.
    """
    available = [h for h, c in counts.items() if c > 0]
    if len(available) < k:
        return None

    chosen: List[int] = []
    temp_counts = counts  # mutate directly after final selection; keep chosen unique via a set

    chosen_set = set()
    for _ in range(k):
        avail = [h for h, c in temp_counts.items() if c > 0 and h not in chosen_set]
        if not avail:
            return None
        w = [temp_counts[h] for h in avail]
        h_pick = weighted_pick_one(rng, avail, w)
        chosen.append(h_pick)
        chosen_set.add(h_pick)

    return chosen


def assign_sessions_to_days(
    rng: random.Random,
    obs_days: List[Tuple[int, str, date]],
    targets: Dict[int, int],
    sessions_per_day: int = 4,
    max_restarts: int = 2000,
) -> Dict[Tuple[int, date], List[int]]:
    """
    Assign 'sessions_per_day' distinct 1-hour sessions to each observation day,
    using the remaining hour-bin target counts.

    Returns mapping: (week_idx, date) -> sorted list of start hours.
    """
    for _ in range(max_restarts):
        remaining = dict(targets)
        mapping: Dict[Tuple[int, date], List[int]] = {}

        # Randomize day order to reduce dead-ends
        days = obs_days[:]
        rng.shuffle(days)

        ok = True
        for (week_idx, _cond, d) in days:
            key = (week_idx, d)

            picks = pick_k_distinct_hours_weighted(rng, remaining, sessions_per_day)
            if picks is None:
                ok = False
                break

            # Check feasibility (all picks must still be available)
            feasible = all(remaining[h] > 0 for h in picks)
            if not feasible:
                ok = False
                break

            # Commit: decrement counts
            for h in picks:
                remaining[h] -= 1

            mapping[key] = sorted(picks)

        # Success only if all hour-bin targets satisfied exactly
        if ok and all(v == 0 for v in remaining.values()) and len(mapping) == len(obs_days):
            return mapping

    raise RuntimeError(
        "Failed to generate a schedule satisfying all constraints and exact hour-bin balance. "
        "Try changing the seed."
    )


def compute_achieved_counts(mapping: Dict[Tuple[int, date], List[int]]) -> Dict[int, int]:
    achieved = {h: 0 for h in range(8, 17)}
    for starts in mapping.values():
        for h in starts:
            achieved[h] += 1
    return achieved


def make_sessions(start_date: date, seed: int) -> Tuple[List[Session], Dict[int, int], Dict[int, int]]:
    # Observation days + conditions (seeded)
    obs_days = build_obs_days(start_date, seed)

    # Targets for hour-bins (seeded but using a separate stream for clarity)
    rng_targets = random.Random(seed + 12345)
    targets = build_balanced_hour_bin_targets(rng_targets)

    # Assign sessions to days (separate RNG stream)
    rng_assign = random.Random(seed + 99991)
    mapping = assign_sessions_to_days(rng_assign, obs_days, targets, sessions_per_day=4)

    achieved = compute_achieved_counts(mapping)

    # Build session rows
    sessions: List[Session] = []
    for (week_idx, cond, d) in obs_days:
        day_name = DAY_NAMES_EN[d.weekday()]
        start_hours = mapping[(week_idx, d)]
        for sess_idx, h in enumerate(start_hours, start=1):
            sessions.append(
                Session(
                    week_index=week_idx,
                    condition=cond,
                    day_date=d,
                    day_name=day_name,
                    session_index=sess_idx,
                    start_hour=h,
                    start_time=fmt_time(h),
                    end_time=fmt_time(h + 1),
                )
            )

    sessions.sort(key=lambda s: (s.week_index, s.day_date, s.start_hour))
    return sessions, targets, achieved


def sanity_checks(sessions: List[Session], targets: Dict[int, int], achieved: Dict[int, int]) -> None:
    # 160 sessions total
    if len(sessions) != 160:
        raise AssertionError(f"Expected 160 sessions, got {len(sessions)}")

    # Week 1 is Control
    week1 = [s for s in sessions if s.week_index == 1]
    if not week1 or week1[0].condition != "Control":
        raise AssertionError("Week 1 is not Control")

    # Week 1: no Monday
    for s in week1:
        if s.day_name == "Monday":
            raise AssertionError("Week 1 includes Monday observation (not allowed)")

    # Per day: 4 distinct sessions
    per_day: Dict[Tuple[int, date], List[Session]] = {}
    for s in sessions:
        per_day.setdefault((s.week_index, s.day_date), []).append(s)

    if len(per_day) != 40:
        raise AssertionError(f"Expected 40 observation days, got {len(per_day)}")

    for key, lst in per_day.items():
        if len(lst) != 4:
            raise AssertionError(f"Day {key} has {len(lst)} sessions, expected 4")
        starts = [x.start_hour for x in lst]
        if len(set(starts)) != 4:
            raise AssertionError(f"Day {key} has overlapping sessions (duplicate start hour).")

    # Hour-bin balance exact
    for h in range(8, 17):
        if achieved[h] != targets[h]:
            raise AssertionError(
                f"Hour-bin {h:02d}:00–{h+1:02d}:00 achieved={achieved[h]} target={targets[h]}"
            )


def print_schedule(sessions: List[Session], start_date: date) -> None:
    by_week: Dict[int, List[Session]] = {}
    for s in sessions:
        by_week.setdefault(s.week_index, []).append(s)

    for week_idx in range(1, 11):
        week_start = start_date + timedelta(days=(week_idx - 1) * 7)
        week_end = week_start + timedelta(days=6)
        cond = by_week[week_idx][0].condition
        print(f"\nWeek {week_idx} ({week_start:%d/%m/%Y}–{week_end:%d/%m/%Y}) — {cond}")

        # group by date
        day_map: Dict[date, List[Session]] = {}
        for s in by_week[week_idx]:
            day_map.setdefault(s.day_date, []).append(s)

        for d in sorted(day_map.keys()):
            lst = sorted(day_map[d], key=lambda x: x.start_hour)
            slots = ", ".join([f"{ss.start_time}–{ss.end_time}" for ss in lst])
            print(f"- {d:%d/%m/%Y} ({DAY_NAMES_EN[d.weekday()]}): {slots}")


def print_hour_bin_summary(targets: Dict[int, int], achieved: Dict[int, int]) -> None:
    ideal = 160 / 9
    print("\nHour-bin coverage summary (1-hour bins):")
    for h in range(8, 17):
        print(f"  {h:02d}:00–{h+1:02d}:00  target={targets[h]:2d}  achieved={achieved[h]:2d}")
    max_dev = max(abs(achieved[h] - ideal) for h in range(8, 17))
    print(f"\nIdeal per bin = {ideal:.2f}; max absolute deviation from ideal = {max_dev:.2f}")


def write_csv(sessions: List[Session], out_path: str) -> None:
    fieldnames = ["week", "condition", "date", "day", "session", "start", "end"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for s in sessions:
            w.writerow(
                {
                    "week": s.week_index,
                    "condition": s.condition,
                    "date": s.day_date.isoformat(),
                    "day": s.day_name,
                    "session": s.session_index,
                    "start": s.start_time,
                    "end": s.end_time,
                }
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True, help="Start date (Monday) of week 1, YYYY-MM-DD")
    ap.add_argument("--seed", type=int, default=18, help="Random seed for reproducibility")
    ap.add_argument("--out", default="sampling_schedule.csv", help="Output CSV path")
    args = ap.parse_args()

    start = parse_iso_date(args.start_date)
    if start.weekday() != 0:
        print(f"Warning: start-date {start.isoformat()} is not a Monday.")

    sessions, targets, achieved = make_sessions(start_date=start, seed=args.seed)
    sanity_checks(sessions, targets, achieved)

    print_schedule(sessions, start_date=start)
    print_hour_bin_summary(targets, achieved)
    write_csv(sessions, args.out)
    print(f"\nCSV written to: {args.out}")


if __name__ == "__main__":
    main()