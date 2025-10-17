#!/usr/bin/env python3
from pathlib import Path
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

# --- Defaults / Schemas ---
JOBS_CSV_DEFAULT = "filament_log.csv"
SPOOLS_CSV_DEFAULT = "filament_spools.csv"

JOB_COLS = ["Date", "Name of Job", "Grams Potential", "Status", "Lost (g)", "Spool ID"]
SPOOL_COLS = ["Spool ID", "Material", "Other Material", "Color", "Other Color", "Spool Size (g)", "Notes", "Created"]

STATUSES = ["init", "success", "failed", "pending"]
MATERIALS = ["PLA", "PETG", "ABS", "ASA", "TPU", "Nylon", "PC", "Composite", "Other"]
COLORS = ["Black", "White", "Gray", "Silver", "Clear", "Red", "Orange", "Yellow", "Green", "Blue", "Purple", "Pink", "Brown", "Other"]

# --- CSV helpers ---
def ensure_csv(path, header):
    p = Path(path)
    if not p.exists():
        with p.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()

def read_rows(path, header):
    ensure_csv(path, header)
    rows = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if header == JOB_COLS and "Spool ID" not in r:
                r["Spool ID"] = ""
            row = {col: r.get(col, "") for col in header}
            # Back-compat: older spools.csv may lack "Other Material"
            if header == SPOOL_COLS and "Other Material" not in r:
                row["Other Material"] = ""
            rows.append(row)
    return rows

def write_rows(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in header})

def safe_float(s):
    try:
        return float(s)
    except:
        return 0.0

# --- Spool ID generation ---
def gen_spool_id(existing_ids):
    date = datetime.now().strftime("%Y%m%d")
    prefix = f"SP-{date}-"
    nums = []
    for sid in existing_ids:
        if sid.startswith(prefix):
            tail = sid.split("-")[-1]
            if tail.isdigit():
                nums.append(int(tail))
    next_num = (max(nums) + 1) if nums else 1
    return f"{prefix}{next_num:04d}"

# --- App ---
class App(tk.Tk):
    def __init__(self, jobs_csv=JOBS_CSV_DEFAULT, spools_csv=SPOOLS_CSV_DEFAULT):
        super().__init__()
        self.title("Filament Track")
        self.geometry("1100x700")
        self.minsize(1000, 640)

        self.jobs_csv = jobs_csv
        self.spools_csv = spools_csv

        self.jobs_rows = read_rows(self.jobs_csv, JOB_COLS)
        self.spools_rows = read_rows(self.spools_csv, SPOOL_COLS)

        # --- Top bar ---
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Jobs CSV:").pack(side=tk.LEFT)
        self.jobs_label = ttk.Label(top, text=self.jobs_csv, foreground="#555")
        self.jobs_label.pack(side=tk.LEFT, padx=(4, 16))

        ttk.Button(top, text="Open Jobs CSV…", command=self.choose_jobs_csv).pack(side=tk.LEFT)
        ttk.Button(top, text="Export Jobs As…", command=lambda: self.export_csv_as(kind="jobs")).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(top, text="Spools CSV:").pack(side=tk.LEFT, padx=(16,4))
        self.spools_label = ttk.Label(top, text=self.spools_csv, foreground="#555")
        self.spools_label.pack(side=tk.LEFT, padx=(4, 16))

        ttk.Button(top, text="Open Spools CSV…", command=self.choose_spools_csv).pack(side=tk.LEFT)
        ttk.Button(top, text="Export Spools As…", command=lambda: self.export_csv_as(kind="spools")).pack(side=tk.LEFT, padx=(6, 0))

        # Totals (right under top bar)
        totals = ttk.LabelFrame(self, text="Totals", padding=8)
        totals.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(4, 8))

        ttk.Label(totals, text="Spool Filter:").pack(side=tk.LEFT)
        self.spool_filter_var = tk.StringVar(value="(All)")
        self.spool_filter_combo = ttk.Combobox(totals, width=24, textvariable=self.spool_filter_var, state="readonly")
        self.spool_filter_combo.pack(side=tk.LEFT, padx=(4,12))
        self.refresh_spool_filter()
        self.spool_filter_combo.bind("<<ComboboxSelected>>", lambda e: self.update_totals())

        self.total_potential_var = tk.StringVar(value="0")
        self.total_consumed_var = tk.StringVar(value="0")
        self.total_lost_var = tk.StringVar(value="0")
        self.spool_remaining_var = tk.StringVar(value="(select a spool)")

        def totals_row(lbl, var):
            f = ttk.Frame(totals)
            f.pack(side=tk.LEFT, padx=12)
            ttk.Label(f, text=lbl).pack(side=tk.TOP, anchor="w")
            ttk.Label(f, textvariable=var, font=("TkDefaultFont", 10, "bold")).pack(side=tk.TOP, anchor="w")

        totals_row("Total potential (g):", self.total_potential_var)
        totals_row("Total consumed (g):", self.total_consumed_var)
        totals_row("Total lost (g):", self.total_lost_var)
        totals_row("Remaining for selected spool (g):", self.spool_remaining_var)

        # --- Notebook ---
        nb = ttk.Notebook(self)
        nb.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0,8))

        # Jobs tab
        jobs_tab = ttk.Frame(nb)
        nb.add(jobs_tab, text="Jobs")

        self.jobs_tree = ttk.Treeview(jobs_tab, columns=JOB_COLS, show="headings", selectmode="browse")
        for col in JOB_COLS:
            self.jobs_tree.heading(col, text=col)
            anchor = tk.W if col not in ("Grams Potential","Lost (g)") else tk.E
            width = 200 if col == "Name of Job" else 130
            self.jobs_tree.column(col, anchor=anchor, width=width, stretch=True)
        self.jobs_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(8,8))

        jb = ttk.Frame(jobs_tab, padding=(8,0,8,8))
        jb.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(jb, text="Add", command=self.add_job).pack(side=tk.LEFT)
        ttk.Button(jb, text="Edit", command=self.edit_job).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(jb, text="Delete", command=self.delete_job).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(jb, text="Save", command=self.save_jobs).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(jb, text="Reload", command=self.reload_jobs).pack(side=tk.LEFT, padx=(6,0))

        # Spools tab
        spools_tab = ttk.Frame(nb)
        nb.add(spools_tab, text="Spools")

        self.spools_tree = ttk.Treeview(spools_tab, columns=SPOOL_COLS, show="headings", selectmode="browse")
        for col in SPOOL_COLS:
            self.spools_tree.heading(col, text=col)
            anchor = tk.W if col not in ("Spool Size (g)",) else tk.E
            width = 160 if col in ("Notes","Other Color") else 150
            self.spools_tree.column(col, anchor=anchor, width=width, stretch=True)
        self.spools_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(8,8))

        sb = ttk.Frame(spools_tab, padding=(8,0,8,8))
        sb.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(sb, text="Add", command=self.add_spool).pack(side=tk.LEFT)
        ttk.Button(sb, text="Edit", command=self.edit_spool).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(sb, text="Delete", command=self.delete_spool).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(sb, text="Save", command=self.save_spools).pack(side=tk.LEFT, padx=(6,0))
        ttk.Button(sb, text="Reload", command=self.reload_spools).pack(side=tk.LEFT, padx=(6,0))

        # Initial loads
        self.reload_jobs()
        self.reload_spools()
        self.update_totals()

    # ---- CSV ops ----
    def choose_jobs_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv"), ("All files","*.*")])
        if not path: return
        self.jobs_csv = path
        self.jobs_label.configure(text=path)
        self.reload_jobs()
        self.update_totals()

    def choose_spools_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv"), ("All files","*.*")])
        if not path: return
        self.spools_csv = path
        self.spools_label.configure(text=path)
        self.reload_spools()
        self.refresh_spool_filter()
        self.update_totals()

    def export_csv_as(self, kind="jobs"):
        header = JOB_COLS if kind=="jobs" else SPOOL_COLS
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")])
        if not path: return
        rows = self.jobs_table_to_rows() if kind=="jobs" else self.spools_table_to_rows()
        try:
            write_rows(path, header, rows)
            messagebox.showinfo("Exported", f"Saved to: {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Jobs ----
    def reload_jobs(self):
        self.jobs_rows = read_rows(self.jobs_csv, JOB_COLS)
        for i in self.jobs_tree.get_children(): self.jobs_tree.delete(i)
        for r in self.jobs_rows:
            self.jobs_tree.insert("", tk.END, values=[r.get(c,"") for c in JOB_COLS])

    def save_jobs(self):
        rows = self.jobs_table_to_rows()
        write_rows(self.jobs_csv, JOB_COLS, rows)
        messagebox.showinfo("Saved", "Jobs CSV saved.")

    def jobs_table_to_rows(self):
        rows = []
        for iid in self.jobs_tree.get_children():
            vals = self.jobs_tree.item(iid, "values")
            rows.append({JOB_COLS[i]: vals[i] for i in range(len(JOB_COLS))})
        return rows

    def add_job(self):
        JobDialog(self, self.spools_rows, title="Add Job", on_ok=self._add_job_row)

    def _add_job_row(self, data):
        self.jobs_tree.insert("", tk.END, values=[data.get(c,"") for c in JOB_COLS])
        self.update_totals()

    def edit_job(self):
        sel = self.jobs_tree.selection()
        if not sel:
            messagebox.showwarning("Select a row", "Choose a job to edit.")
            return
        iid = sel[0]
        values = self.jobs_tree.item(iid, "values")
        JobDialog(self, self.spools_rows, title="Edit Job",
                  initial={JOB_COLS[i]: values[i] for i in range(len(JOB_COLS))},
                  on_ok=lambda d: self._edit_job_row(iid, d))

    def _edit_job_row(self, iid, data):
        self.jobs_tree.item(iid, values=[data.get(c,"") for c in JOB_COLS])
        self.update_totals()

    def delete_job(self):
        sel = self.jobs_tree.selection()
        if not sel: return
        self.jobs_tree.delete(sel[0])
        self.update_totals()

    # ---- Spools ----
    def reload_spools(self):
        self.spools_rows = read_rows(self.spools_csv, SPOOL_COLS)
        for i in self.spools_tree.get_children(): self.spools_tree.delete(i)
        for r in self.spools_rows:
            self.spools_tree.insert("", tk.END, values=[r.get(c,"") for c in SPOOL_COLS])
        self.refresh_spool_filter()

    def save_spools(self):
        rows = self.spools_table_to_rows()
        write_rows(self.spools_csv, SPOOL_COLS, rows)
        messagebox.showinfo("Saved", "Spools CSV saved.")
        self.refresh_spool_filter()
        self.update_totals()

    def spools_table_to_rows(self):
        rows = []
        for iid in self.spools_tree.get_children():
            vals = self.spools_tree.item(iid, "values")
            rows.append({SPOOL_COLS[i]: vals[i] for i in range(len(SPOOL_COLS))})
        return rows

    def add_spool(self):
        existing = [r.get("Spool ID","") for r in self.spools_table_to_rows()]
        default_id = gen_spool_id(existing)
        SpoolDialog(self, title="Add Spool", initial={
            "Spool ID": default_id,
            "Material": "PLA",
            "Color": "Black",
            "Other Color": "",
            "Spool Size (g)": "1000",
            "Notes": "",
            "Created": datetime.now().strftime("%Y-%m-%d"),
        }, on_ok=self._add_spool_row)

    def _add_spool_row(self, data):
        self.spools_tree.insert("", tk.END, values=[data.get(c,"") for c in SPOOL_COLS])
        self.refresh_spool_filter()
        self.update_totals()

    def edit_spool(self):
        sel = self.spools_tree.selection()
        if not sel:
            messagebox.showwarning("Select a row", "Choose a spool to edit.")
            return
        iid = sel[0]
        values = self.spools_tree.item(iid, "values")
        SpoolDialog(self, title="Edit Spool",
                    initial={SPOOL_COLS[i]: values[i] for i in range(len(SPOOL_COLS))},
                    on_ok=lambda d: self._edit_spool_row(iid, d))

    def _edit_spool_row(self, iid, data):
        self.spools_tree.item(iid, values=[data.get(c,"") for c in SPOOL_COLS])
        self.refresh_spool_filter()
        self.update_totals()

    def delete_spool(self):
        sel = self.spools_tree.selection()
        if not sel: return
        self.spools_tree.delete(sel[0])
        self.refresh_spool_filter()
        self.update_totals()

    # ---- Totals & filter ----
    def refresh_spool_filter(self):
        # Build list from cached spools rows (no reliance on Treeview existing yet)
        if not hasattr(self, "spools_rows") or self.spools_rows is None:
            try:
                self.spools_rows = read_rows(self.spools_csv, SPOOL_COLS)
            except Exception:
                self.spools_rows = []
        spools = ["(All)"] + [r.get("Spool ID","") for r in self.spools_rows if r.get("Spool ID","")]
        cur = self.spool_filter_var.get() if hasattr(self, "spool_filter_var") else "(All)"
        if hasattr(self, "spool_filter_combo"):
            self.spool_filter_combo["values"] = spools
        if cur not in spools:
            self.spool_filter_var.set("(All)")

    def update_totals(self):
        rows = self.jobs_table_to_rows()
        filter_sid = self.spool_filter_var.get()
        def passes(r):
            return True if filter_sid == "(All)" else (r.get("Spool ID","") == filter_sid)

        total_potential = 0.0
        total_lost = 0.0
        total_consumed = 0.0

        for r in rows:
            if not passes(r): 
                continue
            potential = safe_float(r.get("Grams Potential",""))
            status = (r.get("Status","") or "").strip().lower()
            lost = safe_float(r.get("Lost (g)",""))
            total_potential += potential
            if status == "success":
                total_consumed += potential
            elif status == "failed":
                total_lost += lost
                total_consumed += lost

        self.total_potential_var.set(f"{total_potential:.2f}")
        self.total_lost_var.set(f"{total_lost:.2f}")
        self.total_consumed_var.set(f"{total_consumed:.2f}")

        # Remaining for selected spool (needs its size)
        if filter_sid != "(All)":
            size = 0.0
            for s in self.spools_table_to_rows():
                if s.get("Spool ID","") == filter_sid:
                    size = safe_float(s.get("Spool Size (g)",""))
                    break
            remaining = max(size - total_consumed, 0.0)
            self.spool_remaining_var.set(f"{remaining:.2f}")
        else:
            self.spool_remaining_var.set("(select a spool)")

# ---- Dialogs ----
class JobDialog(tk.Toplevel):
    def __init__(self, master, spools_rows, title="Job", initial=None, on_ok=None):
        super().__init__(master)
        self.transient(master)
        self.title(title)
        self.resizable(False, False)
        self.on_ok = on_ok

        init = initial or {}

        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", **pad)
        self.date_var = tk.StringVar(value=init.get("Date", datetime.now().strftime("%Y-%m-%d")))
        ttk.Entry(frm, textvariable=self.date_var, width=18).grid(row=0, column=1, **pad)

        ttk.Label(frm, text="Name of Job:").grid(row=1, column=0, sticky="w", **pad)
        self.name_var = tk.StringVar(value=init.get("Name of Job",""))
        ttk.Entry(frm, textvariable=self.name_var, width=40).grid(row=1, column=1, **pad)

        ttk.Label(frm, text="Grams Potential:").grid(row=2, column=0, sticky="w", **pad)
        self.potential_var = tk.StringVar(value=init.get("Grams Potential",""))
        ttk.Entry(frm, textvariable=self.potential_var, width=12).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Status:").grid(row=3, column=0, sticky="w", **pad)
        self.status_var = tk.StringVar(value=init.get("Status","pending"))
        self.status_combo = ttk.Combobox(frm, values=STATUSES, textvariable=self.status_var, width=12, state="readonly")
        self.status_combo.grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Lost (g) if failed:").grid(row=4, column=0, sticky="w", **pad)
        self.lost_var = tk.StringVar(value=init.get("Lost (g)",""))
        ttk.Entry(frm, textvariable=self.lost_var, width=12).grid(row=4, column=1, sticky="w", **pad)

        # Spool picker
        spool_ids = [""] + [r.get("Spool ID","") for r in spools_rows if r.get("Spool ID","")]
        ttk.Label(frm, text="Spool ID:").grid(row=5, column=0, sticky="w", **pad)
        self.spool_var = tk.StringVar(value=init.get("Spool ID",""))
        self.spool_combo = ttk.Combobox(frm, values=spool_ids, textvariable=self.spool_var, width=22, state="readonly")
        self.spool_combo.grid(row=5, column=1, sticky="w", **pad)

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", **pad)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=(6,0))
        ttk.Button(btns, text="OK", command=self.ok).pack(side=tk.RIGHT)

        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def ok(self):
        def is_float(s):
            try: float(s); return True
            except: return False

        date = self.date_var.get().strip()
        name = self.name_var.get().strip()
        potential = self.potential_var.get().strip()
        status = self.status_var.get().strip().lower()
        lost = self.lost_var.get().strip()
        spool_id = self.spool_var.get().strip()

        if not date or not name:
            messagebox.showerror("Missing fields", "Date and Name are required.")
            return
        if potential and not is_float(potential):
            messagebox.showerror("Invalid number", "Grams Potential must be a number.")
            return
        if status not in STATUSES:
            messagebox.showerror("Invalid status", f"Status must be one of: {', '.join(STATUSES)}")
            return
        if status == "failed":
            if not lost or not is_float(lost):
                messagebox.showerror("Missing lost grams", "Please enter Lost (g) for failed prints.")
                return
        else:
            if lost and not is_float(lost):
                messagebox.showerror("Invalid number", "Lost (g) must be a number or blank.")
                return

        data = {
            "Date": date,
            "Name of Job": name,
            "Grams Potential": potential,
            "Status": status,
            "Lost (g)": lost if status == "failed" else "",
            "Spool ID": spool_id
        }
        if self.on_ok:
            self.on_ok(data)
        self.destroy()

class SpoolDialog(tk.Toplevel):
    def __init__(self, master, title="Spool", initial=None, on_ok=None):
        super().__init__(master)
        self.transient(master)
        self.title(title)
        self.resizable(False, False)
        self.on_ok = on_ok

        init = initial or {}

        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill=tk.BOTH, expand=True)

        # Spool ID
        ttk.Label(frm, text="Spool ID:").grid(row=0, column=0, sticky="w", **pad)
        self.id_var = tk.StringVar(value=init.get("Spool ID",""))
        id_row = ttk.Frame(frm)
        id_row.grid(row=0, column=1, sticky="w", **pad)
        ttk.Entry(id_row, textvariable=self.id_var, width=24).pack(side=tk.LEFT)
        ttk.Button(id_row, text="Auto-generate", command=self.auto_id).pack(side=tk.LEFT, padx=(6,0))

        # Material
        ttk.Label(frm, text="Material:").grid(row=1, column=0, sticky="w", **pad)
        self.material_var = tk.StringVar(value=init.get("Material","PLA"))
        self.material_combo = ttk.Combobox(frm, values=MATERIALS, textvariable=self.material_var, width=18, state="readonly")
        self.material_combo.grid(row=1, column=1, sticky="w", **pad)
        self.material_combo.bind("<<ComboboxSelected>>", self.on_material_change)

        # Other Material
        ttk.Label(frm, text="Other Material (if 'Other'):").grid(row=2, column=0, sticky="w", **pad)
        self.other_mat_var = tk.StringVar(value=init.get("Other Material",""))
        self.other_mat_entry = ttk.Entry(frm, textvariable=self.other_mat_var, width=30)
        self.other_mat_entry.grid(row=2, column=1, sticky="w", **pad)

        # Color
        ttk.Label(frm, text="Color:").grid(row=3, column=0, sticky="w", **pad)
        self.color_var = tk.StringVar(value=init.get("Color","Black"))
        self.color_combo = ttk.Combobox(frm, values=COLORS, textvariable=self.color_var, width=18, state="readonly")
        self.color_combo.grid(row=3, column=1, sticky="w", **pad)
        self.color_combo.bind("<<ComboboxSelected>>", self.on_color_change)

        # Other Color
        ttk.Label(frm, text="Other Color (if 'Other'):").grid(row=4, column=0, sticky="w", **pad)
        self.other_color_var = tk.StringVar(value=init.get("Other Color",""))
        self.other_color_entry = ttk.Entry(frm, textvariable=self.other_color_var, width=30)
        self.other_color_entry.grid(row=4, column=1, sticky="w", **pad)

        # Spool Size
        ttk.Label(frm, text="Spool Size (g):").grid(row=5, column=0, sticky="w", **pad)
        self.size_var = tk.StringVar(value=init.get("Spool Size (g)","1000"))
        ttk.Entry(frm, textvariable=self.size_var, width=12).grid(row=5, column=1, sticky="w", **pad)

        # Notes
        ttk.Label(frm, text="Notes:").grid(row=6, column=0, sticky="w", **pad)
        self.notes_var = tk.StringVar(value=init.get("Notes",""))
        ttk.Entry(frm, textvariable=self.notes_var, width=40).grid(row=6, column=1, sticky="w", **pad)

        # Created
        ttk.Label(frm, text="Created (YYYY-MM-DD):").grid(row=7, column=0, sticky="w", **pad)
        self.created_var = tk.StringVar(value=init.get("Created", datetime.now().strftime("%Y-%m-%d")))
        ttk.Entry(frm, textvariable=self.created_var, width=18).grid(row=7, column=1, sticky="w", **pad)

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e", **pad)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=(6,0))
        ttk.Button(btns, text="OK", command=self.ok).pack(side=tk.RIGHT)

        # Initialize visibility
        self.on_material_change()
        self.on_color_change()

        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def auto_id(self):
        rows = self.master.spools_table_to_rows()
        existing = [r.get("Spool ID","") for r in rows]
        self.id_var.set(gen_spool_id(existing))

    def on_material_change(self, event=None):
        """Show/hide Other Material field based on selection"""
        if self.material_var.get() == "Other":
            self.other_mat_entry.config(state="normal")
        else:
            self.other_mat_entry.config(state="disabled")
            self.other_mat_var.set("")

    def on_color_change(self, event=None):
        """Show/hide Other Color field based on selection"""
        if self.color_var.get() == "Other":
            self.other_color_entry.config(state="normal")
        else:
            self.other_color_entry.config(state="disabled")
            self.other_color_var.set("")

    def ok(self):
        def is_float(s):
            try: float(s); return True
            except: return False

        sid = self.id_var.get().strip()
        mat = self.material_var.get().strip()
        other_mat = self.other_mat_var.get().strip()
        col = self.color_var.get().strip()
        other = self.other_color_var.get().strip()
        size = self.size_var.get().strip()
        notes = self.notes_var.get().strip()
        created = self.created_var.get().strip()

        if not sid:
            messagebox.showerror("Missing Spool ID", "Spool ID is required.")
            return
        if not size or not is_float(size):
            messagebox.showerror("Invalid size", "Spool Size (g) must be a number.")
            return
        if mat == "Other" and not other_mat:
            messagebox.showerror("Missing material", "Please enter Other Material.")
            return
        if col == "Other" and not other:
            messagebox.showerror("Missing color", "Please enter Other Color.")
            return

        data = {
            "Spool ID": sid,
            "Material": mat,
            "Other Material": other_mat if mat == "Other" else "",
            "Color": col,
            "Other Color": other if col == "Other" else "",
            "Spool Size (g)": size,
            "Notes": notes,
            "Created": created
        }
        if self.on_ok:
            self.on_ok(data)
        self.destroy()

if __name__ == "__main__":
    import sys
    jobs_csv = JOBS_CSV_DEFAULT
    spools_csv = SPOOLS_CSV_DEFAULT
    if len(sys.argv) > 1:
        jobs_csv = sys.argv[1]
    if len(sys.argv) > 2:
        spools_csv = sys.argv[2]
    # Ensure CSVs exist with headers
    if not Path(jobs_csv).exists():
        with open(jobs_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=JOB_COLS)
            writer.writeheader()
    else:
        # If 'Spool ID' is missing in existing jobs file, rewrite header and keep data
        with open(jobs_csv, "r", newline="") as f:
            reader = csv.DictReader(f)
            had_spool = ("Spool ID" in reader.fieldnames) if reader.fieldnames else False
            rows = list(reader)
        if not had_spool:
            with open(jobs_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=JOB_COLS)
                writer.writeheader()
                for r in rows:
                    r["Spool ID"] = ""
                    writer.writerow({c: r.get(c, "") for c in JOB_COLS})
    if not Path(spools_csv).exists():
        with open(spools_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SPOOL_COLS)
            writer.writeheader()
    else:
        with open(spools_csv, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fields = reader.fieldnames or []
        if "Other Material" not in fields:
            with open(spools_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=SPOOL_COLS)
                writer.writeheader()
                for r in rows:
                    r = {**{k:"" for k in SPOOL_COLS}, **r}
                    if not r.get("Other Material") and r.get("Material") != "Other":
                        r["Other Material"] = ""
                    writer.writerow({c: r.get(c, "") for c in SPOOL_COLS})

    app = App(jobs_csv=jobs_csv, spools_csv=spools_csv)
    app.mainloop()