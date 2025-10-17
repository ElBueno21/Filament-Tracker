# Filament Track

A desktop app to log and total 3D‑printer filament usage with **just CSV files** with **multi‑spool tracking**.

- **Tech:** Python + Tkinter
- **Storage:** CSV (no DB, no cloud)
- **Platforms:** Windows, macOS, Linux

---

## Quick Start

1. **Install Python 3** (and Tkinter if needed)
2. **Run**:
   ```bash
   python3 filament_tracker.py filament_log.csv filament_spools.csv
   ```
   - If you omit the CSV arguments, the app will use/create them in the current folder.
3. **Add a Spool** (Spools tab)
   - Click **Add**, pick **Material** or **Other** → type custom material, choose a **Color** or **Other** → type custom color
   - Set **Spool Size (g)** (e.g., 1000)
   - **Spool ID** auto‑generates; you can regenerate or edit before saving
4. **Add a Job** (Jobs tab)
   - Fill **Date**, **Name**, **Grams Potential**, **Status**
   - Select **Spool ID** for the spool you used
   - If **failed**, enter **Lost (g)**
5. **Totals**
   - Use the **Spool Filter** to see totals & remaining for that spool
   - **Remaining on spool** = `Spool Size (g) − Consumed on that spool`

---

## CSV Schemas

### `filament_spools.csv`
```
Spool ID,Material,Other Material,Color,Other Color,Spool Size (g),Notes,Created
```
- **Spool ID**: like `SP-YYYYMMDD-####` (unique)
- **Material**: PLA, PETG, ABS, ASA, TPU, Nylon, PC, Composite, Other
- **Other Material**: free text (used when Material = Other)
- **Color**: Black, White, Gray, Silver, Clear, Red, Orange, Yellow, Green, Blue, Purple, Pink, Brown, Other
- **Other Color**: free text (used when Color = Other)
- **Spool Size (g)**: e.g., 1000 for a 1 kg spool
- **Notes**: optional
- **Created**: `YYYY-MM-DD`

### `filament_log.csv` (jobs)
```
Date,Name of Job,Grams Potential,Status,Lost (g),Spool ID
```
- **Status**: `init | success | failed | pending`
- **Lost (g)**: only required when `failed`
- **Spool ID**: optional, but needed for per‑spool totals

> Existing rows without **Spool ID** still load fine. Assign a spool whenever you like.

---

## Totals math

- **Total potential (g)** = Σ “Grams Potential”
- **Total lost (g)** = Σ “Lost (g)” where `Status = failed`
- **Total consumed (g)** = Σ “Grams Potential” for `success` + Σ “Lost (g)” for `failed`
- **Remaining for spool S (g)** = `Spool Size (g)` − (consumed on S)

---

## Troubleshooting

- **Tkinter not found** on Linux? Install it:
  ```bash
  sudo apt update
  sudo apt install python3-tk
  ```
- **CSV locked** by Excel? Close the file in Excel before hitting **Save** in the app.
- **Weird numbers?** Ensure the numeric cells (Grams Potential, Lost (g)) are plain numbers (no “g” suffix).

---

## License

MIT – use it, tweak it, ship it.
