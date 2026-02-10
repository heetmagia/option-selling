# -*- coding: utf-8 -*-
"""
NIFTY Intraday Option Selling - REALTIME (WebSocket Driven)
Author: Heet Magia
"""

#websocket driven intraday option selling strategy for NIFTY 50 index .

from upstox_api.api import Upstox, WebSocket
from datetime import datetime, time
import time as tm
import pytz
import pandas as pd

# =========================
# CONFIG
# =========================
API_KEY = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"

LOT_SIZE = 50
LOTS_PER_TRADE = 2
QTY = LOT_SIZE * LOTS_PER_TRADE

STOPLOSS_PCT = 0.50
MAX_LOSS = -25000

START_TIME = time(10, 0, 0)
END_ENTRY_TIME = time(14, 45, 0)
FORCE_EXIT_TIME = time(14, 59, 0)

IST = pytz.timezone("Asia/Kolkata")

# =========================
# INIT UPSTOX
# =========================
u = Upstox(API_KEY, API_SECRET)
u.set_access_token(ACCESS_TOKEN)

# =========================
# STATE
# =========================
spot_price = None
last_trade_minute = None
sl_hit_today = False
kill_switch_active = False
trades = []

# =========================
# LOGGING
# =========================
def log_trade(data):
    trades.append(data)
    pd.DataFrame(trades).to_csv("trade_log.csv", index=False)

# =========================
# ORDER HELPERS
# =========================
def wait_for_fill(order_id, wait_sec=5):
    start = tm.time()
    while tm.time() - start <= wait_sec:
        od = u.get_order_details(order_id)
        if od["status"] == "complete":
            return float(od["average_price"]), int(od["filled_quantity"])
        if od["status"] == "rejected":
            return None, None
        tm.sleep(1)
    return None, None


def sell_market(token):
    o = u.place_order(
        transaction_type="SELL",
        instrument_token=token,
        quantity=QTY,
        order_type="MARKET",
        product="I",
        duration="DAY"
    )
    return o["order_id"]


def place_sl(token, sl_price, qty):
    sl_price = round(sl_price / 0.05) * 0.05
    o = u.place_order(
        transaction_type="BUY",
        instrument_token=token,
        quantity=qty,
        order_type="SL-M",
        product="I",
        trigger_price=sl_price,
        duration="DAY"
    )
    return o["order_id"]


def force_exit_all():
    positions = u.get_positions()
    for p in positions:
        if p["quantity"] != 0 and p["product"] == "I":
            txn = "BUY" if p["quantity"] < 0 else "SELL"
            u.place_order(
                transaction_type=txn,
                instrument_token=p["instrument_token"],
                quantity=abs(p["quantity"]),
                order_type="MARKET",
                product="I",
                duration="DAY"
            )

# =========================
# KILL SWITCH
# =========================
def update_kill_switch():
    global kill_switch_active
    pnl = sum(p["pnl"] for p in u.get_positions())
    if pnl <= MAX_LOSS:
        kill_switch_active = True
        force_exit_all()
        print("🚨 KILL SWITCH TRIGGERED:", pnl)

# =========================
# STRATEGY CORE
# =========================
def try_trade():
    global last_trade_minute, sl_hit_today

    now = datetime.now(IST).time()

    if now >= FORCE_EXIT_TIME:
        force_exit_all()
        return

    if not (START_TIME <= now <= END_ENTRY_TIME):
        return

    if sl_hit_today or kill_switch_active:
        return

    if now.minute % 15 != 0 or last_trade_minute == now.minute:
        return

    last_trade_minute = now.minute

    # =========================
    # STRIKE SELECTION (CUSTOMISE HERE)
    # =========================
    ce_strike = round((spot_price + 300) / 50) * 50
    pe_strike = round((spot_price - 300) / 50) * 50

    instruments = u.get_instruments("NFO")

    for opt_type, strike in [("CE", ce_strike), ("PE", pe_strike)]:
        opt = next(
            i for i in instruments
            if i["strike_price"] == strike
            and i["instrument_type"] == opt_type
            and i["tradingsymbol"].startswith("NIFTY")
        )

        order_id = sell_market(opt["instrument_token"])
        avg, qty = wait_for_fill(order_id)

        if not avg:
            continue

        sl_price = avg * (1 + STOPLOSS_PCT)
        sl_id = place_sl(opt["instrument_token"], sl_price, qty)

        log_trade({
            "time": datetime.now(IST),
            "strike": strike,
            "type": opt_type,
            "entry_price": avg,
            "qty": qty,
            "entry_order": order_id,
            "sl_order": sl_id
        })

        update_kill_switch()

# =========================
# WEBSOCKET HANDLERS
# =========================
def on_tick(ws, tick):
    global spot_price
    spot_price = tick["ltp"]
    try_trade()


def on_connect(ws):
    print("✅ WebSocket Connected")
    ws.subscribe([u.get_instrument_by_symbol("NSE_INDEX", "NIFTY 50")["instrument_token"]])
    ws.set_mode(ws.MODE_LTP, [u.get_instrument_by_symbol("NSE_INDEX", "NIFTY 50")["instrument_token"]])


# =========================
# START WEBSOCKET
# =========================
ws = WebSocket(u, on_tick, on_connect)
ws.connect()
