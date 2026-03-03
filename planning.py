import random
import datetime
import csv
import argparse
from collections import Counter
from pathlib import Path

# --------------------------------------------------
# PARAMETERS
# --------------------------------------------------

WEEKS = 10
DAYS_PER_WEEK = 4
SESSIONS_PER_DAY = 4
START_HOUR = 9
END_HOUR = 17  # last session is 16:00–17:00
HOUR_BINS = list(range(START_HOUR, END_HOUR))  # 9–16 (8 bins)

EXCLUDED_DATE = datetime.date(2026, 3, 3)  # exclude Tuesday 03/03/2026


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def format_date(d: datetime.date) -> str:
    return d.strftime("%d/%m/%Y")


def week_range_str(week_start: datetime.date) -> str:
    week_end = week_start + datetime.timedelta(days=6)
    return f"{format_date(week_start)}–{format_date(week_end)}"


# --------------------------------------------------
# CONDITIONS
# --------------------------------------------------

def generate_conditions(rng: random.Random):
    # 5 Control + 5 Natural, Week 1 forced to Control
    conditions = ["Control"] * 5 + ["Natural"] * 5
    conditions.remove("Control")
    rng.shuffle(conditions)
    return ["Control"] + conditions


# --------------------------------------------------
# DATES
# --------------------------------------------------

def generate_week_dates(start_date: datetime.date):
    all_weeks = []
    for w in range(WEEKS):
        week_start = start_date + datetime.timedelta(weeks=w)
        week_dates = [week_start + datetime.timedelta(days=i) for i in range(7)]
        all_weeks.append(week_dates)
    return all_weeks


# --------------------------------------------------
# HOUR-BIN ASSIGNMENT (perfect balance: 160 sessions / 8 bins = 20 each)
# --------------------------------------------------

def assign_sessions_balanced(rng: random.Random):
    total_sessions = WEEKS * DAYS_PER_WEEK * SESSIONS_PER_DAY  # 160
    if total_sessions % len(HOUR_BINS) != 0:
        raise RuntimeError("Total sessions not divisible by number of hour-bins.")

    target_per_bin = total_sessions // len(HOUR_BINS)  # 20
    bin_pool = []
    for h in HOUR_BINS:
        bin_pool.extend([h] * target_per_bin)

    rng.shuffle(bin_pool)
    targets = {h: target_per_bin for h in HOUR_BINS}
    return bin_pool, targets


# --------------------------------------------------
# SCHEDULE GENERATION
# --------------------------------------------------

def generate_schedule(start_date: datetime.date, seed: int):
    rng = random.Random(seed)

    conditions = generate_conditions(rng)
    all_weeks = generate_week_dates(start_date)
    bin_pool, targets = assign_sessions_balanced(rng)

    schedule_rows = []  # for CSV (flat list)
    schedule_by_week = []  # for terminal printing (structured)
    assigned_hours = []
    bin_index = 0

    for w in range(WEEKS):
        week_dates = all_weeks[w]
        week_start = week_dates[0]

        possible_days = week_dates.copy()

        # Exclude Monday in Week 1 (installation)
        if w == 0:
            possible_days = [d for d in possible_days if d.weekday() != 0]

        # Exclude specific date 03/03/2026
        possible_days = [d for d in possible_days if d != EXCLUDED_DATE]

        if len(possible_days) < DAYS_PER_WEEK:
            raise RuntimeError(
                f"Not enough available days in Week {w+1} after exclusions."
            )

        selected_days = sorted(rng.sample(possible_days, DAYS_PER_WEEK))

        week_block = {
            "week": w + 1,
            "condition": conditions[w],
            "range": week_range_str(week_start),
            "days": []
        }

        for day in selected_days:
            sessions = []
            for _ in range(SESSIONS_PER_DAY):
                hour = bin_pool[bin_index]
                bin_index += 1
                assigned_hours.append(hour)
                sessions.append((hour, f"{hour:02d}:00–{hour+1:02d}:00"))

            sessions.sort(key=lambda x: x[0])
            session_str = ", ".join(s for _, s in sessions)

            # For CSV
            schedule_rows.append([
                w + 1,
                conditions[w],
                format_date(day),
                session_str
            ])

            # For terminal output
            week_block["days"].append((day, session_str))

        schedule_by_week.append(week_block)

    achieved = Counter(assigned_hours)
    total_sessions = WEEKS * DAYS_PER_WEEK * SESSIONS_PER_DAY
    ideal = total_sessions / len(HOUR_BINS)  # 20.0 exactly here
    max_abs_dev = max(abs(achieved.get(h, 0) - ideal) for h in HOUR_BINS)

    return schedule_rows, schedule_by_week, targets, achieved, ideal, max_abs_dev


# --------------------------------------------------
# OUTPUT: CSV
# --------------------------------------------------

def save_schedule_csv(schedule_rows, filename: str):
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Week", "Condition", "Date", "Sessions"])
        w.writerows(schedule_rows)


def save_hourbin_csv(targets, achieved, ideal: float, max_abs_dev: float, filename: str):
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Hour-bin", "Target", "Achieved"])
        for h in HOUR_BINS:
            w.writerow([f"{h:02d}:00–{h+1:02d}:00", targets[h], achieved.get(h, 0)])
        w.writerow([])
        w.writerow(["Ideal per bin", f"{ideal:.2f}", ""])
        w.writerow(["Max absolute deviation from ideal", f"{max_abs_dev:.2f}", ""])


# --------------------------------------------------
# OUTPUT: TERMINAL PRINTING
# --------------------------------------------------

def print_schedule(schedule_by_week):
    print("\n" + "=" * 72)
    print("OBSERVATION SCHEDULE")
    print("=" * 72)

    for wb in schedule_by_week:
        print(f"\nWeek {wb['week']} ({wb['range']}) — {wb['condition']}")
        for day, sessions in wb["days"]:
            # Example: 04/03/2026 (Wednesday): 09:00–10:00, ...
            print(f"  - {format_date(day)} ({day.strftime('%A')}): {sessions}")

    print("\n" + "=" * 72 + "\n")


def print_hourbin_summary(targets, achieved, ideal: float, max_abs_dev: float):
    print("Hour-bin coverage summary (1-hour bins):")
    for h in HOUR_BINS:
        print(f"  {h:02d}:00–{h+1:02d}:00  target={targets[h]}  achieved={achieved.get(h, 0)}")
    print(f"\nIdeal per bin = {ideal:.2f}; max absolute deviation from ideal = {max_abs_dev:.2f}\n")


# --------------------------------------------------
# RUN
# --------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD (start of Week 1; ideally a Monday)")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True, help="Schedule CSV output filename (e.g., schedule.csv)")
    parser.add_argument(
        "--hourbin-out",
        default=None,
        help="Optional hour-bin summary CSV output filename (default: <out>_hourbins.csv)"
    )
    args = parser.parse_args()

    start = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()

    schedule_rows, schedule_by_week, targets, achieved, ideal, max_abs_dev = generate_schedule(start, args.seed)

    # Print to terminal
    print_schedule(schedule_by_week)
    print_hourbin_summary(targets, achieved, ideal, max_abs_dev)

    # Save CSV outputs
    save_schedule_csv(schedule_rows, args.out)
    out_path = Path(args.out)
    hourbin_out = args.hourbin_out or str(out_path.with_name(out_path.stem + "_hourbins.csv"))
    save_hourbin_csv(targets, achieved, ideal, max_abs_dev, hourbin_out)

    print("Files written:")
    print(f"  - {args.out}")
    print(f"  - {hourbin_out}")
