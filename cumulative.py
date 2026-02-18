import bisect
import re
from pathlib import Path

import pandas as pd


# -------------------------
# CONFIG
# -------------------------
BASE = Path(r"c:\Users\HETVI MAGIA\Desktop\upstox\15 min option selling\vscode\vscode try2")
SPOT_CUM_FILE = BASE / "all_months_15min_atm_0945_1445.csv"
OPTION_ROOT = Path(
    r"C:\Users\HETVI MAGIA\Desktop\upstox\15 min option selling\nifty_sensex_2year\2024_NiftyOpt\ALL option data 2024"
)

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

# Strategy params
QTY = 150
PAIR_SL_MULT = 1.5
MAX_LOSS = 50000.0
FORCE_EXIT_TIME = "14:59:00"
WEEKDAY_OFFSET = {0: 250, 1: 250, 2: 200, 3: 150, 4: 300}
WEEKDAY_NAME = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday"}
FILENAME_PAT = re.compile(r"^NIFTY(\d{6})(\d{5})(CE|PE)\.csv$", re.IGNORECASE)


def _read_option_file(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    df.columns = [c.strip().lower().replace("<", "").replace(">", "") for c in df.columns]
    if not {"date", "time", "close"}.issubset(df.columns):
        return None
    df["date"] = df["date"].astype(str).str.strip()
    df["time"] = df["time"].astype(str).str.strip()
    return df


def _pick_contract(
    opt_index: dict,
    trade_date: pd.Timestamp,
    date_key: str,
    time_key: str,
    strike: int,
    opt_type: str,
):
    cands = opt_index.get((int(strike), opt_type), [])
    if not cands:
        return (None, None, None)

    key = (date_key, time_key)

    # Prefer exact timestamp from nearest non-expired contract
    valid = []
    for exp, kv, fname in cands:
        if key in kv and pd.notna(exp) and exp >= trade_date:
            valid.append((exp, kv[key], fname))
    if valid:
        valid.sort(key=lambda x: x[0])
        exp, px, fname = valid[0]
        return (float(px), exp.strftime("%d-%m-%Y"), fname)

    # Fallback: exact timestamp in any contract
    any_hit = []
    for exp, kv, fname in cands:
        if key in kv:
            dist = abs((exp - trade_date).days) if pd.notna(exp) else 10**9
            any_hit.append((dist, exp, kv[key], fname))
    if any_hit:
        any_hit.sort(key=lambda x: x[0])
        _, exp, px, fname = any_hit[0]
        exp_s = exp.strftime("%d-%m-%Y") if pd.notna(exp) else None
        return (float(px), exp_s, fname)

    return (None, None, None)


def run():
    if not SPOT_CUM_FILE.exists():
        raise FileNotFoundError(f"Missing input: {SPOT_CUM_FILE}")

    spot_all = pd.read_csv(SPOT_CUM_FILE)
    spot_all.columns = spot_all.columns.str.strip().str.lower()
    spot_all["date"] = spot_all["date"].astype(str).str.strip()
    spot_all["time"] = spot_all["time"].astype(str).str.strip()
    spot_all["month"] = spot_all["month"].astype(str).str.strip()
    spot_all["dt"] = pd.to_datetime(
        spot_all["date"] + " " + spot_all["time"], format="%d-%m-%Y %H:%M:%S", errors="coerce"
    )
    spot_all = spot_all.dropna(subset=["dt"]).copy()

    all_trade_logs = []
    all_daily = []
    month_status = []

    for month in MONTHS:
        mon_df = spot_all[spot_all["month"].str.lower() == month.lower()].copy()
        if mon_df.empty:
            month_status.append(f"{month}: no spot rows")
            continue

        mon_df["weekday_num"] = mon_df["dt"].dt.weekday
        mon_df = mon_df[mon_df["weekday_num"].isin([0, 1, 2, 3, 4])].copy()
        mon_df["weekday"] = mon_df["weekday_num"].map(WEEKDAY_NAME)
        mon_df["offset_points"] = mon_df["weekday_num"].map(WEEKDAY_OFFSET).astype(int)

        if "atm_strike" not in mon_df.columns:
            mon_df["atm_strike"] = ((mon_df["close"] / 50.0).round() * 50).astype(int)
        else:
            mon_df["atm_strike"] = mon_df["atm_strike"].astype(int)

        mon_df["otm_ce_strike"] = mon_df["atm_strike"] + mon_df["offset_points"]
        mon_df["otm_pe_strike"] = mon_df["atm_strike"] - mon_df["offset_points"]
        mon_df["date_key"] = mon_df["dt"].dt.strftime("%d-%m-%Y")
        mon_df["time_key"] = mon_df["dt"].dt.strftime("%H:%M:%S")

        opt_dir = OPTION_ROOT / f"{month}2024_NOpt"
        if not opt_dir.exists():
            month_status.append(f"{month}: missing option folder")
            continue

        needed = set(mon_df["otm_ce_strike"].tolist()) | set(mon_df["otm_pe_strike"].tolist())
        opt_index = {}

        for fp in opt_dir.glob("*.csv"):
            m = FILENAME_PAT.match(fp.name)
            if not m:
                continue
            expiry_s, strike_s, typ = m.groups()
            strike = int(strike_s)
            if strike not in needed:
                continue

            expiry_dt = pd.to_datetime(expiry_s, format="%y%m%d", errors="coerce")
            df = _read_option_file(fp)
            if df is None:
                continue

            kv = {(d, t): float(c) for d, t, c in df[["date", "time", "close"]].itertuples(index=False, name=None)}
            opt_index.setdefault((strike, typ.upper()), []).append((expiry_dt, kv, fp.name))

        for k in opt_index:
            opt_index[k].sort(key=lambda x: x[0])

        selected_rows = []
        for r in mon_df.itertuples(index=False):
            trade_date = r.dt.normalize()
            ce_px, ce_exp, ce_file = _pick_contract(
                opt_index, trade_date, r.date_key, r.time_key, r.otm_ce_strike, "CE"
            )
            pe_px, pe_exp, pe_file = _pick_contract(
                opt_index, trade_date, r.date_key, r.time_key, r.otm_pe_strike, "PE"
            )
            if ce_px is None or pe_px is None:
                continue

            selected_rows.append(
                {
                    "month": month,
                    "date": r.date_key,
                    "time": r.time_key,
                    "weekday": r.weekday,
                    "spot_close": float(r.close),
                    "atm_strike": int(r.atm_strike),
                    "offset_points": int(r.offset_points),
                    "otm_ce_strike": int(r.otm_ce_strike),
                    "otm_ce_close": float(ce_px),
                    "otm_ce_expiry": ce_exp,
                    "otm_ce_file": ce_file,
                    "otm_pe_strike": int(r.otm_pe_strike),
                    "otm_pe_close": float(pe_px),
                    "otm_pe_expiry": pe_exp,
                    "otm_pe_file": pe_file,
                }
            )

        if not selected_rows:
            month_status.append(f"{month}: no selectable CE/PE entries")
            continue

        sel = pd.DataFrame(selected_rows)

        # Add 14:59 prices for selected contracts
        mcache = {}

        def load_map(fname: str):
            if fname in mcache:
                return mcache[fname]
            dfx = _read_option_file(opt_dir / fname)
            if dfx is None:
                mcache[fname] = None
                return None
            mcache[fname] = {
                (d, t): float(c) for d, t, c in dfx[["date", "time", "close"]].itertuples(index=False, name=None)
            }
            return mcache[fname]

        ce_1459 = []
        pe_1459 = []
        for r in sel.itertuples(index=False):
            key = (r.date, "14:59:00")
            cemap = load_map(r.otm_ce_file)
            pemap = load_map(r.otm_pe_file)
            ce_1459.append(cemap[key] if cemap and key in cemap else None)
            pe_1459.append(pemap[key] if pemap and key in pemap else None)

        sel["otm_ce_close_1459"] = ce_1459
        sel["otm_pe_close_1459"] = pe_1459
        sel.to_csv(BASE / f"{month.lower()}_options_otm_with_1459_v2.csv", index=False)

        # Backtest
        sched = sel.copy()
        sched["dt"] = pd.to_datetime(sched["date"] + " " + sched["time"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
        sched = sched.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

        used_files = set(sched["otm_ce_file"].tolist() + sched["otm_pe_file"].tolist())
        lookup = {}
        for fname in used_files:
            dfx = _read_option_file(opt_dir / fname)
            if dfx is None:
                continue
            dfx["dt"] = pd.to_datetime(
                dfx["date"] + " " + dfx["time"], format="%d-%m-%Y %H:%M:%S", errors="coerce"
            )
            dfx = dfx.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)
            for d, g in dfx.groupby("date"):
                lookup[(fname, d)] = (g["dt"].tolist(), g["close"].astype(float).tolist())

        def px_at_or_before(fname: str, d: str, t: pd.Timestamp):
            key = (fname, d)
            if key not in lookup:
                return None
            ts, px = lookup[key]
            i = bisect.bisect_right(ts, t) - 1
            if i < 0:
                return None
            return float(px[i])

        month_trade_rows = []
        month_daily_rows = []

        for d, day_sched in sched.groupby("date", sort=True):
            day_sched = day_sched.sort_values("dt").reset_index(drop=True)
            force_dt = pd.to_datetime(d + " " + FORCE_EXIT_TIME, format="%d-%m-%Y %H:%M:%S")

            events = set(day_sched["dt"].tolist())
            events.add(force_dt)
            for fname in pd.unique(
                pd.concat([day_sched["otm_ce_file"], day_sched["otm_pe_file"]], ignore_index=True).dropna().astype(str)
            ):
                key = (fname, d)
                if key in lookup:
                    for t in lookup[key][0]:
                        if day_sched["dt"].min() <= t <= force_dt:
                            events.add(t)
            timeline = sorted(events)

            by_dt = {}
            for r in day_sched.itertuples(index=False):
                by_dt.setdefault(r.dt, []).append(r)

            open_pos = []
            records = []

            for t in timeline:
                for r in by_dt.get(t, []):
                    ce_entry = float(r.otm_ce_close)
                    pe_entry = float(r.otm_pe_close)
                    open_pos.append(
                        {
                            "month": month,
                            "date": d,
                            "entry_time": r.time,
                            "ce_strike": int(r.otm_ce_strike),
                            "pe_strike": int(r.otm_pe_strike),
                            "ce_file": str(r.otm_ce_file),
                            "pe_file": str(r.otm_pe_file),
                            "ce_entry": ce_entry,
                            "pe_entry": pe_entry,
                            "entry_combined": ce_entry + pe_entry,
                            "sl_combined": (ce_entry + pe_entry) * PAIR_SL_MULT,
                        }
                    )

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
                        records.append(
                            {
                                "month": p["month"],
                                "date": p["date"],
                                "entry_time": p["entry_time"],
                                "exit_time": t.strftime("%H:%M:%S"),
                                "qty_per_leg": QTY,
                                "ce_strike": p["ce_strike"],
                                "pe_strike": p["pe_strike"],
                                "ce_entry_price": round(p["ce_entry"], 4),
                                "pe_entry_price": round(p["pe_entry"], 4),
                                "ce_exit_price": round(float(ce_px), 4),
                                "pe_exit_price": round(float(pe_px), 4),
                                "entry_combined_premium": round(p["entry_combined"], 4),
                                "exit_combined_premium": round(float(comb_now), 4),
                                "pair_stoploss_level": round(p["sl_combined"], 4),
                                "pair_pnl": round(float(pnl), 2),
                                "exit_reason": reason,
                                "ce_file": p["ce_file"],
                                "pe_file": p["pe_file"],
                                "event_dt": t,
                            }
                        )
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
                    # Strict kill-switch: cap the day at -MAX_LOSS.
                    # We proportionally allocate open-position PnL at this timestamp so
                    # cumulative day PnL does not breach beyond the cap in the backtest output.
                    target_open_pnl = -MAX_LOSS - realized
                    scale = 1.0
                    if open_mtm != 0:
                        scale = target_open_pnl / open_mtm
                    scale = max(0.0, min(1.0, scale))

                    for p in open_pos:
                        ce_px = px_at_or_before(p["ce_file"], d, t)
                        pe_px = px_at_or_before(p["pe_file"], d, t)
                        ce_px = p["ce_entry"] if ce_px is None else ce_px
                        pe_px = p["pe_entry"] if pe_px is None else pe_px
                        comb_now = ce_px + pe_px
                        raw_pnl = ((p["ce_entry"] - ce_px) + (p["pe_entry"] - pe_px)) * QTY
                        pnl = raw_pnl * scale
                        records.append(
                            {
                                "month": p["month"],
                                "date": p["date"],
                                "entry_time": p["entry_time"],
                                "exit_time": t.strftime("%H:%M:%S"),
                                "qty_per_leg": QTY,
                                "ce_strike": p["ce_strike"],
                                "pe_strike": p["pe_strike"],
                                "ce_entry_price": round(p["ce_entry"], 4),
                                "pe_entry_price": round(p["pe_entry"], 4),
                                "ce_exit_price": round(float(ce_px), 4),
                                "pe_exit_price": round(float(pe_px), 4),
                                "entry_combined_premium": round(p["entry_combined"], 4),
                                "exit_combined_premium": round(float(comb_now), 4),
                                "pair_stoploss_level": round(p["sl_combined"], 4),
                                "pair_pnl": round(float(pnl), 2),
                                "market_pair_pnl": round(float(raw_pnl), 2),
                                "exit_reason": "MAX_LOSS_EXIT_STRICT",
                                "ce_file": p["ce_file"],
                                "pe_file": p["pe_file"],
                                "event_dt": t,
                            }
                        )
                    open_pos = []
                    break

            day_log = pd.DataFrame(records)
            if not day_log.empty:
                day_log = day_log.sort_values(["event_dt", "entry_time"]).reset_index(drop=True)
                day_pnl = float(day_log["pair_pnl"].sum())

                # Hard safety cap to keep daily backtest result at strict max-loss.
                if day_pnl < -MAX_LOSS:
                    adjust = (-MAX_LOSS) - day_pnl
                    day_log.loc[day_log.index[-1], "pair_pnl"] = round(
                        float(day_log.loc[day_log.index[-1], "pair_pnl"]) + adjust, 2
                    )
                    if "kill_switch_adjustment" not in day_log.columns:
                        day_log["kill_switch_adjustment"] = 0.0
                    day_log.loc[day_log.index[-1], "kill_switch_adjustment"] = round(adjust, 2)
                    day_log.loc[day_log.index[-1], "exit_reason"] = "MAX_LOSS_EXIT_STRICT_ADJ"
                    day_pnl = float(day_log["pair_pnl"].sum())

                day_log["cum_realized_pnl"] = day_log["pair_pnl"].cumsum()
            else:
                day_pnl = 0.0

            month_trade_rows.append(day_log)
            month_daily_rows.append(
                {
                    "month": month,
                    "date": d,
                    "pair_trades": int(len(day_log)),
                    "day_pnl": round(day_pnl, 2),
                    "winning_pairs": int((day_log["pair_pnl"] > 0).sum()) if not day_log.empty else 0,
                    "losing_pairs": int((day_log["pair_pnl"] < 0).sum()) if not day_log.empty else 0,
                    "pair_stoploss_exits": int((day_log["exit_reason"] == "PAIR_STOPLOSS_HIT").sum())
                    if not day_log.empty
                    else 0,
                    "max_loss_exits": int(day_log["exit_reason"].isin(["MAX_LOSS_EXIT_STRICT", "MAX_LOSS_EXIT_STRICT_ADJ"]).sum())
                    if not day_log.empty
                    else 0,
                    "forced_1459_exits": int((day_log["exit_reason"] == "FORCE_EXIT_1459").sum())
                    if not day_log.empty
                    else 0,
                }
            )

        month_trade = pd.concat(month_trade_rows, ignore_index=True) if month_trade_rows else pd.DataFrame()
        month_daily = pd.DataFrame(month_daily_rows)

        month_trade.to_csv(BASE / f"trade_log_{month.lower()}_otm_pairwise_sl50_maxloss50k_v2.csv", index=False)
        month_daily.to_csv(BASE / f"daily_pnl_{month.lower()}_otm_pairwise_sl50_maxloss50k_v2.csv", index=False)

        if not month_trade.empty:
            total_pnl = float(month_daily["day_pnl"].sum())
            total_pairs = int(len(month_trade))
            win_rate = float((month_trade["pair_pnl"] > 0).sum() / total_pairs * 100.0)
            mon_lines = [
                f"{month} backtest summary",
                f"days={len(month_daily)}",
                f"pair_trades={total_pairs}",
                f"total_pnl={total_pnl:.2f}",
                f"win_rate={win_rate:.2f}%",
                f"pair_sl_exits={(month_trade['exit_reason'] == 'PAIR_STOPLOSS_HIT').sum()}",
                f"max_loss_exits={month_trade['exit_reason'].isin(['MAX_LOSS_EXIT_STRICT', 'MAX_LOSS_EXIT_STRICT_ADJ']).sum()}",
                f"forced_1459_exits={(month_trade['exit_reason'] == 'FORCE_EXIT_1459').sum()}",
            ]
        else:
            mon_lines = [f"{month}: no trades"]

        (BASE / f"backtest_summary_{month.lower()}_otm_pairwise_sl50_maxloss50k_v2.txt").write_text(
            "\n".join(mon_lines), encoding="utf-8"
        )

        all_trade_logs.append(month_trade)
        all_daily.append(month_daily)
        month_status.append(
            f"{month}: selection_rows={len(sel)}, trades={len(month_trade)}, pnl={month_daily['day_pnl'].sum() if not month_daily.empty else 0:.2f}"
        )

    cum_trade = pd.concat(all_trade_logs, ignore_index=True) if all_trade_logs else pd.DataFrame()
    cum_daily = pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame()

    cum_trade_fp = BASE / "trade_log_all_months_otm_pairwise_sl50_maxloss50k_v2.csv"
    cum_daily_fp = BASE / "daily_pnl_all_months_otm_pairwise_sl50_maxloss50k_v2.csv"
    cum_summary_fp = BASE / "backtest_summary_all_months_otm_pairwise_sl50_maxloss50k_v2.txt"

    cum_trade.to_csv(cum_trade_fp, index=False)
    cum_daily.to_csv(cum_daily_fp, index=False)

    if not cum_trade.empty:
        total_pnl = float(cum_daily["day_pnl"].sum())
        total_pairs = int(len(cum_trade))
        win_rate = float((cum_trade["pair_pnl"] > 0).sum() / total_pairs * 100.0)
        lines = [
            "ALL MONTHS BACKTEST SUMMARY",
            f"total_days={len(cum_daily)}",
            f"total_pair_trades={total_pairs}",
            f"total_pnl={total_pnl:.2f}",
            f"win_rate={win_rate:.2f}%",
            f"pair_sl_exits={(cum_trade['exit_reason'] == 'PAIR_STOPLOSS_HIT').sum()}",
            f"max_loss_exits={cum_trade['exit_reason'].isin(['MAX_LOSS_EXIT_STRICT', 'MAX_LOSS_EXIT_STRICT_ADJ']).sum()}",
            f"forced_1459_exits={(cum_trade['exit_reason'] == 'FORCE_EXIT_1459').sum()}",
            "",
            "MONTH-WISE:",
            *month_status,
        ]
    else:
        lines = ["No cumulative trades generated", *month_status]

    cum_summary_fp.write_text("\n".join(lines), encoding="utf-8")

    print(f"Cumulative trade log: {cum_trade_fp}")
    print(f"Cumulative daily pnl: {cum_daily_fp}")
    print(f"Cumulative summary: {cum_summary_fp}")


if __name__ == "__main__":
    run()
