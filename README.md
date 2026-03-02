# Sunbittern Sampling Schedule Randomization

## Overview

This repository contains the Python script (`planning.py`) used to generate a constrained randomized sampling schedule for a 10-week behavioral study on captive Sunbitterns (*Eurypyga helias*).

The script was designed to:
- Randomize the order of experimental conditions (Control / Natural)
- Randomly select observation days within each week
- Schedule 1-hour observation sessions between 08:00 and 17:00
- Balance observation effort across all available hourly time bins
- Ensure full reproducibility via a fixed random seed

The script was developed using Python 3.13 in Spyder and executed under Windows 10.

---

## Experimental Design Constraints Implemented

The script enforces the following constraints:

- Total duration: 10 consecutive weeks
- Experimental conditions: 5 Control weeks, 5 Natural weeks
- Week 1 is fixed as Control  
  (logistical justification: experimental nests were constructed and installed during Week 1)
- 4 observation days per week (randomly selected)
- Mondays excluded during Week 1
- 4 non-overlapping 1-hour sessions per observation day
- Observation window: 08:00–17:00 (start times between 08:00 and 16:00)
- Total observation effort: 160 hours

---

## Hour-Bin Balancing

To minimize temporal sampling bias, the script balances observation effort across nine 1-hour time bins:

08:00–09:00  
09:00–10:00  
10:00–11:00  
11:00–12:00  
12:00–13:00  
13:00–14:00  
14:00–15:00  
15:00–16:00  
16:00–17:00  

Because 160 sessions cannot be perfectly divided across 9 bins (160/9 = 17.78), the algorithm distributes:

- 18 sessions to 7 bins  
- 17 sessions to 2 bins  

This represents the most mathematically even possible distribution.

---

## Reproducibility

The schedule is fully reproducible using a fixed random seed.

Command used to generate the study schedule:

cd $HOME\Desktop  
python planning.py --start-date 2026-03-02 --seed 33 --out schedule.csv  

Parameters:
- `--start-date` : Monday corresponding to Week 1 (YYYY-MM-DD format)
- `--seed` : Random seed for reproducibility
- `--out` : Name of the generated CSV file

---

## Output

The script generates:

- A printed weekly schedule in the terminal
- A CSV file containing:
  - Week number
  - Experimental condition
  - Date
  - Day
  - Session index
  - Start time
  - End time
- An hour-bin coverage summary
- The maximum absolute deviation from ideal temporal balance

---

## Software Environment

- Python 3.13
- Spyder IDE
- Windows 10
- Standard Python libraries only (no external dependencies)

---

## Citation

If used or adapted, please cite:

Stan (2026). Sunbittern sampling randomization script (Version 1.0). Zenodo. DOI: https://doi.org/10.5281/zenodo.18827241

---

## License

This project is released under the MIT License.
