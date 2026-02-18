#15 min option selling backtest


import bisect
import re
from pathlib import Path
import pandas as pd

# -------------------------
# CONFIG
# -------------------------
BASE_DIR = Path(r"c:\Users\HETVI MAGIA\Desktop\upstox\15 min option selling\vscode\vscode try2")
JAN_SPOT_FILE = Path(
    r"C:\Users\HETVI MAGIA\Desktop\upstox\15 min option selling\nifty_sensex_2year\2024_NiftyOpt\Nifty Spot Data\extracted\January\.NSEI.csv"
)
JAN_OPT_DIR = Path(
    r"C:\Users\HETVI MAGIA\Desktop\upstox\15 min option selling\nifty_sensex_2year\2024_NiftyOpt\ALL option data 2024\January2024_NOpt"
)

SPOT_15MIN_FILE = BASE_DIR / "january_15min_0945_1445.csv"
OTM_FILE = BASE_DIR / "january_options_atm_pm500_15min.csv"  # kept same name as your flow
OTM_1459_FILE = BASE_DIR / "january_options_otm_with_1459.csv"

PAIR_LOG = BASE_DIR / "trade_log_january_otm_pairwise_sl50_maxloss50k.csv"
PAIR_DAILY = BASE_DIR / "daily_pnl_january_otm_pairwise_sl50_maxloss50k.csv"
PAIR_SUMMARY = BASE_DIR / "backtest_summary_january_otm_pairwise_sl50_maxloss50k.txt"

QTY = 150
PAIR_SL_MULT = 1.5
MAX_LOSS = 50000.0
FORCE_EXIT_TIME = "14:59:00"

# Monday=0 ... Friday=4
WEEKDAY_OFFSET = {0: 250, 1: 250, 2: 200, 3: 150, 4: 300}
WEEKDAY_NAME = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday"}

SLOTS = [
    "09:45:00", "10:00:00", "10:15:00", "10:30:00", "10:45:00",
    "11:00:00", "11:15:00", "11:30:00", "11:45:00",
    "12:00:00", "12:15:00", "12:30:00", "12:45:00",
    "13:00:00", "13:15:00", "13:30:00", "13:45:00",
    "14:00:00", "14:15:00", "14:30:00", "14:45:00",
]


# -------------------------
# STEP 1: Extract Jan spot 15-min
# -------------------------
def build_january_15min_spot():
    df = pd.read_csv(JAN_SPOT_FILE)
    df.columns = df.columns.str.strip().str.lower()

    out = df[df["time"].astype(str).str.strip().isin(SLOTS)][["date", "time", "close"]].copy()
    out["dt"] = pd.to_datetime(out["date"] + " " + out["time"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
    out = out.sort_values("dt").drop(columns=["dt"])
    out.to_csv(SPOT_15MIN_FILE, index=False)
    print(f"Wrote {SPOT_15MIN_FILE} rows={len(out)}")


# -------------------------
# STEP 2 + STEP 3: ATM + OTM by weekday offset
# -------------------------
def build_otm_sheet():
    spot = pd.read_csv(SPOT_15MIN_FILE)
    spot.columns = spot.columns.str.strip().str.lower()
    if "atm_strike" not in spot.columns:
        spot["atm_strike"] = ((spot["close"] / 50.0).round() * 50).astype(int)

    spot["dt"] = pd.to_datetime(spot["date"] + " " + spot["time"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
    spot = spot.dropna(subset=["dt"]).copy()
    spot["weekday_num"] = spot["dt"].dt.weekday
    spot = spot[spot["weekday_num"].isin([0, 1, 2, 3, 4])].copy()

    spot["weekday"] = spot["weekday_num"].map(WEEKDAY_NAME)
    spot["offset_points"] = spot["weekday_num"].map(WEEKDAY_OFFSET).astype(int)
    spot["otm_ce_strike"] = spot["atm_strike"].astype(int) + spot["offset_points"]
    spot["otm_pe_strike"] = spot["atm_strike"].astype(int) - spot["offset_points"]
    spot["date_key"] = spot["dt"].dt.strftime("%d-%m-%Y")
    spot["time_key"] = spot["dt"].dt.strftime("%H:%M:%S")

    needed = set(spot["otm_ce_strike"].tolist()) | set(spot["otm_pe_strike"].tolist())

    pat = re.compile(r"^NIFTY(\d{6})(\d{5})(CE|PE)\.csv$", re.IGNORECASE)
    file_meta = []
    for fp in JAN_OPT_DIR.glob("*.csv"):
        m = pat.match(fp.name)
        if not m:
            continue
        expiry_yyMMdd, strike_s, opt_type = m.groups()
        strike = int(strike_s)
        if strike not in needed:
            continue
        expiry_dt = pd.to_datetime(expiry_yyMMdd, format="%y%m%d", errors="coerce")
        file_meta.append((fp, expiry_dt, strike, opt_type.upper()))

    opt_index = {}
    for fp, exp_dt, strike, opt_type in file_meta:
        df = pd.read_csv(fp)
        df.columns = [c.strip().lower().replace("<", "").replace(">", "") for c in df.columns]
        if not {"date", "time", "close"}.issubset(df.columns):
            continue
        df["date"] = df["date"].astype(str).str.strip()
        df["time"] = df["time"].astype(str).str.strip()
        kv = {(d, t): c for d, t, c in df[["date", "time", "close"]].itertuples(index=False, name=None)}
        opt_index.setdefault((strike, opt_type), []).append((exp_dt, kv, fp.name))

    for k in opt_index:
        opt_index[k].sort(key=lambda x: x[0])

    def pick_price(trade_date, date_key, time_key, strike, opt_type):
        candidates = opt_index.get((int(strike), opt_type), [])
        if not candidates:
            return (None, None, None)
        key = (date_key, time_key)

        valid = []
        for exp, kv, fname in candidates:
            if key in kv and pd.notna(exp) and exp >= trade_date:
                valid.append((exp, kv[key], fname))
        if valid:
            valid.sort(key=lambda x: x[0])
            exp, px, fname = valid[0]
            return (float(px), exp.strftime("%d-%m-%Y"), fname)

        any_hit = []
        for exp, kv, fname in candidates:
            if key in kv:
                dist = abs((exp - trade_date).days) if pd.notna(exp) else 10**9
                any_hit.append((dist, exp, kv[key], fname))
        if any_hit:
            any_hit.sort(key=lambda x: x[0])
            _, exp, px, fname = any_hit[0]
            exp_s = exp.strftime("%d-%m-%Y") if pd.notna(exp) else None
            return (float(px), exp_s, fname)

        return (None, None, None)

    rows = []
    for r in spot.itertuples(index=False):
        trade_date = r.dt.normalize()
        ce_px, ce_exp, ce_file = pick_price(trade_date, r.date_key, r.time_key, r.otm_ce_strike, "CE")
        pe_px, pe_exp, pe_file = pick_price(trade_date, r.date_key, r.time_key, r.otm_pe_strike, "PE")

        rows.append({
            "date": r.date_key,
            "time": r.time_key,
            "weekday": r.weekday,
            "spot_close": r.close,
            "atm_strike": int(r.atm_strike),
            "offset_points": int(r.offset_points),
            "otm_ce_strike": int(r.otm_ce_strike),
            "otm_ce_close": ce_px,
            "otm_ce_expiry": ce_exp,
            "otm_ce_file": ce_file,
            "otm_pe_strike": int(r.otm_pe_strike),
            "otm_pe_close": pe_px,
            "otm_pe_expiry": pe_exp,
            "otm_pe_file": pe_file,
        })

    out = pd.DataFrame(rows)
    out.to_csv(OTM_FILE, index=False)
    print(f"Wrote {OTM_FILE} rows={len(out)}")


# -------------------------
# STEP 4: Add 14:59 close of same selected contracts
# -------------------------
def add_1459_prices():
    df = pd.read_csv(OTM_FILE)
    cache = {}

    def file_map(fname):
        if pd.isna(fname) or not str(fname).strip():
            return None
        fname = str(fname).strip()
        if fname in cache:
            return cache[fname]
        fp = JAN_OPT_DIR / fname
        if not fp.exists():
            cache[fname] = None
            return None
        x = pd.read_csv(fp)
        x.columns = [c.strip().lower().replace("<", "").replace(">", "") for c in x.columns]
        if not {"date", "time", "close"}.issubset(x.columns):
            cache[fname] = None
            return None
        x["date"] = x["date"].astype(str).str.strip()
        x["time"] = x["time"].astype(str).str.strip()
        cache[fname] = {(d, t): c for d, t, c in x[["date", "time", "close"]].itertuples(index=False, name=None)}
        return cache[fname]

    ce_1459, pe_1459 = [], []
    for r in df.itertuples(index=False):
        key = (str(r.date).strip(), "14:59:00")
        ce_map = file_map(getattr(r, "otm_ce_file", None))
        pe_map = file_map(getattr(r, "otm_pe_file", None))
        ce_1459.append(float(ce_map[key]) if ce_map and key in ce_map else None)
        pe_1459.append(float(pe_map[key]) if pe_map and key in pe_map else None)

    df["otm_ce_close_1459"] = ce_1459
    df["otm_pe_close_1459"] = pe_1459
    df.to_csv(OTM_1459_FILE, index=False)
    print(f"Wrote {OTM_1459_FILE} rows={len(df)}")


# -------------------------
# STEP 5: Pairwise backtest (CE+PE together)
# -------------------------
def backtest_pairwise():
    sched = pd.read_csv(OTM_1459_FILE)
    sched.columns = sched.columns.str.strip()
    sched["date"] = sched["date"].astype(str).str.strip()
    sched["time"] = sched["time"].astype(str).str.strip()
    sched["dt"] = pd.to_datetime(sched["date"] + " " + sched["time"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
    sched = sched.dropna(subset=["dt"]).copy()
    sched = sched[(sched["dt"].dt.time >= pd.to_datetime("09:45:00").time()) & (sched["dt"].dt.time <= pd.to_datetime("14:45:00").time())]
    sched = sched.sort_values("dt").reset_index(drop=True)

    needed_files = set(sched["otm_ce_file"].dropna().astype(str).tolist() + sched["otm_pe_file"].dropna().astype(str).tolist())
    cache = {}
    lookup = {}
    for fname in needed_files:
        fp = JAN_OPT_DIR / fname
        if not fp.exists():
            continue
        x = pd.read_csv(fp)
        x.columns = [c.strip().lower().replace("<", "").replace(">", "") for c in x.columns]
        if not {"date", "time", "close"}.issubset(x.columns):
            continue
        x["date"] = x["date"].astype(str).str.strip()
        x["time"] = x["time"].astype(str).str.strip()
        x["dt"] = pd.to_datetime(x["date"] + " " + x["time"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
        x = x.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)
        cache[fname] = x
        for d, g in x.groupby("date"):
            lookup[(fname, d)] = (g["dt"].tolist(), g["close"].astype(float).tolist())

    def px_at_or_before(fname, d, t):
        key = (fname, d)
        if key not in lookup:
            return None
        ts, px = lookup[key]
        i = bisect.bisect_right(ts, t) - 1
        return None if i < 0 else float(px[i])

    pair_rows, daily_rows = [], []

    for d, day in sched.groupby("date", sort=True):
        day = day.sort_values("dt").reset_index(drop=True)
        force_dt = pd.to_datetime(d + " " + FORCE_EXIT_TIME, format="%d-%m-%Y %H:%M:%S")
        events = set(day["dt"].tolist()) | {force_dt}

        for fname in pd.unique(pd.concat([day["otm_ce_file"], day["otm_pe_file"]], ignore_index=True).dropna().astype(str)):
            key = (fname, d)
            if key in lookup:
                for t in lookup[key][0]:
                    if day["dt"].min() <= t <= force_dt:
                        events.add(t)
        timeline = sorted(events)

        by_dt = {}
        for r in day.itertuples(index=False):
            by_dt.setdefault(r.dt, []).append(r)

        open_pos, records = [], []

        for t in timeline:
            if t in by_dt:
                for r in by_dt[t]:
                    ce_entry = float(r.otm_ce_close)
                    pe_entry = float(r.otm_pe_close)
                    open_pos.append({
                        "date": d, "entry_time": r.time, "entry_dt": r.dt,
                        "ce_strike": int(r.otm_ce_strike), "pe_strike": int(r.otm_pe_strike),
                        "ce_file": str(r.otm_ce_file), "pe_file": str(r.otm_pe_file),
                        "ce_entry": ce_entry, "pe_entry": pe_entry,
                        "entry_combined": ce_entry + pe_entry,
                        "sl_combined": (ce_entry + pe_entry) * PAIR_SL_MULT,
                    })

            still_open = []
            for p in open_pos:
                ce_px = px_at_or_before(p["ce_file"], d, t)
                pe_px = px_at_or_before(p["pe_file"], d, t)

                if ce_px is None or pe_px is None:
                    if t >= force_dt:
                        ce_px = p["ce_entry"] if ce_px is None else ce_px
                        pe_px = p["pe_entry"] if pe_px is None else pe_px
                    else:
                        still_open.append(p)
                        continue

                comb_now = ce_px + pe_px
                pnl = ((p["ce_entry"] - ce_px) + (p["pe_entry"] - pe_px)) * QTY

                if comb_now >= p["sl_combined"] or t >= force_dt:
                    reason = "PAIR_STOPLOSS_HIT" if comb_now >= p["sl_combined"] else "FORCE_EXIT_1459"
                    records.append({
                        "date": p["date"], "entry_time": p["entry_time"], "exit_time": t.strftime("%H:%M:%S"),
                        "qty_per_leg": QTY, "ce_strike": p["ce_strike"], "pe_strike": p["pe_strike"],
                        "ce_entry_price": round(p["ce_entry"], 4), "pe_entry_price": round(p["pe_entry"], 4),
                        "ce_exit_price": round(float(ce_px), 4), "pe_exit_price": round(float(pe_px), 4),
                        "entry_combined_premium": round(p["entry_combined"], 4),
                        "exit_combined_premium": round(float(comb_now), 4),
                        "pair_stoploss_level": round(p["sl_combined"], 4),
                        "pair_pnl": round(float(pnl), 2), "exit_reason": reason,
                        "ce_file": p["ce_file"], "pe_file": p["pe_file"], "event_dt": t,
                    })
                else:
                    still_open.append(p)
            open_pos = still_open

            realized = sum(x["pair_pnl"] for x in records)
            open_mtm = 0.0
            for p in open_pos:
                ce_px = px_at_or_before(p["ce_file"], d, t)
                pe_px = px_at_or_before(p["pe_file"], d, t)
                ce_px = p["ce_entry"] if ce_px is None else ce_px
                pe_px = p["pe_entry"] if pe_px is None else pe_px
                open_mtm += ((p["ce_entry"] - ce_px) + (p["pe_entry"] - pe_px)) * QTY

            if realized + open_mtm <= -MAX_LOSS:
                for p in open_pos:
                    ce_px = px_at_or_before(p["ce_file"], d, t)
                    pe_px = px_at_or_before(p["pe_file"], d, t)
                    ce_px = p["ce_entry"] if ce_px is None else ce_px
                    pe_px = p["pe_entry"] if pe_px is None else pe_px
                    comb_now = ce_px + pe_px
                    pnl = ((p["ce_entry"] - ce_px) + (p["pe_entry"] - pe_px)) * QTY
                    records.append({
                        "date": p["date"], "entry_time": p["entry_time"], "exit_time": t.strftime("%H:%M:%S"),
                        "qty_per_leg": QTY, "ce_strike": p["ce_strike"], "pe_strike": p["pe_strike"],
                        "ce_entry_price": round(p["ce_entry"], 4), "pe_entry_price": round(p["pe_entry"], 4),
                        "ce_exit_price": round(float(ce_px), 4), "pe_exit_price": round(float(pe_px), 4),
                        "entry_combined_premium": round(p["entry_combined"], 4),
                        "exit_combined_premium": round(float(comb_now), 4),
                        "pair_stoploss_level": round(p["sl_combined"], 4),
                        "pair_pnl": round(float(pnl), 2), "exit_reason": "MAX_LOSS_EXIT",
                        "ce_file": p["ce_file"], "pe_file": p["pe_file"], "event_dt": t,
                    })
                open_pos = []
                break

        day_df = pd.DataFrame(records)
        if not day_df.empty:
            day_df = day_df.sort_values(["event_dt", "entry_time"]).reset_index(drop=True)
            day_df["cum_realized_pnl"] = day_df["pair_pnl"].cumsum()
            day_pnl = float(day_df["pair_pnl"].sum())
        else:
            day_pnl = 0.0

        pair_rows.append(day_df)
        daily_rows.append({
            "date": d, "pair_trades": int(len(day_df)), "day_pnl": round(day_pnl, 2),
            "winning_pairs": int((day_df["pair_pnl"] > 0).sum()) if not day_df.empty else 0,
            "losing_pairs": int((day_df["pair_pnl"] < 0).sum()) if not day_df.empty else 0,
            "pair_stoploss_exits": int((day_df["exit_reason"] == "PAIR_STOPLOSS_HIT").sum()) if not day_df.empty else 0,
            "max_loss_exits": int((day_df["exit_reason"] == "MAX_LOSS_EXIT").sum()) if not day_df.empty else 0,
            "forced_1459_exits": int((day_df["exit_reason"] == "FORCE_EXIT_1459").sum()) if not day_df.empty else 0,
        })

    pair_log = pd.concat(pair_rows, ignore_index=True) if pair_rows else pd.DataFrame()
    daily = pd.DataFrame(daily_rows)
    pair_log.to_csv(PAIR_LOG, index=False)
    daily.to_csv(PAIR_DAILY, index=False)

    if not pair_log.empty:
        total_pnl = daily["day_pnl"].sum()
        total_pairs = len(pair_log)
        win_pairs = (pair_log["pair_pnl"] > 0).sum()
        win_rate = (win_pairs / total_pairs) * 100.0 if total_pairs else 0.0
        lines = [
            "BACKTEST SUMMARY - JAN OTM COMBINED CE+PE",
            "Model: CE+PE entered together; exited together",
            f"Total days: {len(daily)}",
            f"Total pair trades: {total_pairs}",
            f"Total PnL: {total_pnl:.2f}",
            f"Win rate: {win_rate:.2f}%",
            f"Pair SL exits: {(pair_log['exit_reason'] == 'PAIR_STOPLOSS_HIT').sum()}",
            f"Max-loss exits: {(pair_log['exit_reason'] == 'MAX_LOSS_EXIT').sum()}",
            f"Forced 14:59 exits: {(pair_log['exit_reason'] == 'FORCE_EXIT_1459').sum()}",
            f"Trade log: {PAIR_LOG}",
            f"Daily: {PAIR_DAILY}",
        ]
    else:
        lines = ["No records generated."]
    PAIR_SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {PAIR_LOG}, {PAIR_DAILY}, {PAIR_SUMMARY}")


if __name__ == "__main__":
    build_january_15min_spot()
    build_otm_sheet()
    add_1459_prices()
    backtest_pairwise()
