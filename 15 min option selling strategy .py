# -*- coding: utf-8 -*-
"""
Created on Fri Feb  6 15:51:36 2026

@author: HETVI MAGIA
"""


import pandas as pd
from datetime import time

# ======================
# PARAMETERS
# ======================
LOT_SIZE = 50
LOTS_PER_TRADE = 2
STOPLOSS_PCT = 0.50

START_TIME = time(10, 0)
END_ENTRY_TIME = time(14, 45)
FORCE_EXIT_TIME = time(14, 59)

# ======================
# LOAD DATA
# ======================
df = pd.read_csv("nifty_options.csv", parse_dates=["datetime", "expiry"])
df["date"] = df["datetime"].dt.date
df["time"] = df["datetime"].dt.time

# ======================
# BACKTEST STORAGE
# ======================
trades = []

# ======================
# MAIN BACKTEST LOOP
# ======================
for trading_date in df["date"].unique():

    day_data = df[df["date"] == trading_date]

    # nearest expiry
    expiry = day_data["expiry"].min()

    day_data = day_data[day_data["expiry"] == expiry]

    open_positions = []

    for _, row in day_data.iterrows():

        current_time = row["time"]
        
        
        
        

        # ENTRY EVERY 15 MIN
        if (
            START_TIME <= current_time <= END_ENTRY_TIME
            and row["datetime"].minute % 15 == 0
        ):

            spot = day_data[
                day_data["datetime"] == row["datetime"]
            ]["close"].mean()  # proxy if spot not available

            ce_strike = round((spot + 300) / 50) * 50
            pe_strike = round((spot - 300) / 50) * 50

            for opt_type, strike in [("CE", ce_strike), ("PE", pe_strike)]:

                opt = day_data[
                    (day_data["strike"] == strike) &
                    (day_data["option_type"] == opt_type) &
                    (day_data["datetime"] == row["datetime"])
                ]

                if opt.empty:
                    continue

                entry_price = opt.iloc[0]["close"]

                open_positions.append({
                    "entry_time": row["datetime"],
                    "strike": strike,
                    "type": opt_type,
                    "entry_price": entry_price,
                    "sl_price": entry_price * (1 + STOPLOSS_PCT),
                    "qty": LOT_SIZE * LOTS_PER_TRADE,
                    "open": True
                })




        # CHECK SL
        for pos in open_positions:
            if not pos["open"]:
                continue

            opt_price = day_data[
                (day_data["strike"] == pos["strike"]) &
                (day_data["option_type"] == pos["type"]) &
                (day_data["datetime"] == row["datetime"])
            ]

            if opt_price.empty:
                continue

            ltp = opt_price.iloc[0]["close"]

            if ltp >= pos["sl_price"]:
                pos["open"] = False
                trades.append({
                    **pos,
                    "exit_time": row["datetime"],
                    "exit_price": ltp,
                    "reason": "SL"
                })





        # FORCE EXIT
        
        if current_time >= FORCE_EXIT_TIME:
            for pos in open_positions:
                if pos["open"]:
                    opt_price = day_data[
                        (day_data["strike"] == pos["strike"]) &
                        (day_data["option_type"] == pos["type"]) &
                        (day_data["datetime"] == row["datetime"])
                    ]
                    if opt_price.empty:
                        continue

                    ltp = opt_price.iloc[0]["close"]
                    pos["open"] = False
                    trades.append({
                        **pos,
                        "exit_time": row["datetime"],
                        "exit_price": ltp,
                        "reason": "TIME"
                    })



def kill_switch():
    positions = order_api.get_positions().data

    for pos in positions:
        if pos.quantity != 0 and pos.product == "I":
            txn = "BUY" if pos.quantity < 0 else "SELL"

            order = PlaceOrderRequest(
                quantity=abs(pos.quantity),
                product="I",
                validity="DAY",
                price=0,
                tag="KILL_SWITCH",
                instrument_token=pos.instrument_token,
                order_type="MARKET",
                transaction_type=txn,
                disclosed_quantity=0,
                trigger_price=0,
                is_amo=False
            )

            order_api.place_order(order)

    print("🔥 KILL SWITCH ACTIVATED — ALL POSITIONS CLOSED")



# ======================
# RESULTS
# ======================
trades_df = pd.DataFrame(trades)
trades_df["pnl"] = (
    trades_df["entry_price"] - trades_df["exit_price"]
) * trades_df["qty"]

print(trades_df.groupby("reason")["pnl"].sum())
print("TOTAL PNL:", trades_df["pnl"].sum())


def get_open_positions():
    positions = order_api.get_positions().data

    open_positions = [
        pos for pos in positions if pos.quantity != 0
    ]

    return open_positions


open_pos = get_open_positions()

for pos in open_pos:
    print(
        pos.instrument_token,
        pos.quantity,
        pos.pnl,
        pos.day_buy_value,
        pos.day_sell_value
    )


def get_total_pnl():
    positions = order_api.get_positions().data
    total_pnl = sum(pos.pnl for pos in positions)
    return round(total_pnl, 2)


def get_intraday_pnl():
    positions = order_api.get_positions().data
    day_pnl = sum(pos.day_buy_value - pos.day_sell_value for pos in positions)
    return round(day_pnl, 2)

def has_open_position():
    positions = order_api.get_positions().data
    return any(pos.quantity != 0 for pos in positions)


MAX_LOSS = -15000  # example

def risk_check_and_kill():
    pnl = get_total_pnl()
    if pnl <= MAX_LOSS:
        print("🚨 MAX LOSS HIT:", pnl)
        kill_switch()


#LIVE DASHBOARD
import streamlit as st




