# NIFTY 15-Minute Option Selling Strategy

A Python-based automated trading system for selling NIFTY options using the Upstox API. This strategy enters short positions every 15 minutes during market hours and exits based on stop loss or end-of-day conditions.

## 📊 Strategy Overview

### Entry Logic
- **Entry Interval**: Every 15 minutes between 10:00 AM - 2:45 PM
- **Entry Type**: Simultaneous short positions on Call (CE) and Put (PE) options
- **Strike Selection**: Sells options ₹300 above and below the current spot price
- **Lot Size**: 50 contracts per position
- **Quantity per Trade**: 100 contracts (2 lots)

### Exit Logic
1. **Stop Loss**: Triggered at 0.50% loss on position
2. **Time-based Exit**: Forces all positions closed at 2:59 PM
3. **Max Loss Limit**: Automated kill switch at ₹-37,000 loss

## 🚀 Quick Start

### Prerequisites
```bash
python 3.8+
pip install upstox-client pandas
```

### Installation
```bash
git clone https://github.com/yourusername/nifty-option-selling.git
cd nifty-option-selling
pip install -r requirements.txt
```

### Configuration
1. Copy `config.example.py` to `config.py`:
```bash
cp config.example.py config.py
```

2. Add your Upstox API credentials to `config.py`:
```python
API_KEY = "your_actual_api_key"
CLIENT_ID = "your_client_id"
```

### Prepare Data
Ensure you have two CSV files in the project directory:
- `nifty_options.csv` - Options chain data
- `nifty_spot.csv` - Spot price data

See [Data Format](#data-format) for specifications.

### Run Backtest
```bash
python backtest.py  # (Can be created to analyze historical trades)
```

### Run Live Strategy
```bash
python "15 min option selling strategy .py"
```

## 📁 Project Structure

```
nifty-option-selling/
├── 15 min option selling strategy .py  # Main trading script
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── config.example.py                   # Configuration template
├── config.py                           # (Not in repo) Your credentials
├── nifty_options.csv                   # Options chain data
├── nifty_spot.csv                      # Spot data
├── trade_log.csv                       # Auto-generated trades
├── .gitignore                          # Git ignore rules
└── DATA_FORMAT.md                      # CSV format specification
```

## 📈 Trade Log Format

The strategy auto-generates `trade_log.csv` with the following columns:

| Column | Type | Description |
|--------|------|-------------|
| date | date | Trading date |
| time | datetime | Entry timestamp |
| strike | float | Strike price |
| type | str | CE or PE |
| entry_price | float | Average fill price |
| qty | int | Executed quantity |
| entry_order_id | str | Order ID |
| sl_order_id | str | Stop loss order ID |

### Sample Trade Log
```
date,time,strike,type,entry_price,qty,entry_order_id,sl_order_id
2025-02-10,2025-02-10 10:00:00,23000,CE,125.50,100,ORD001,ORD002
2025-02-10,2025-02-10 10:00:00,22700,PE,98.25,100,ORD003,ORD004
```

## ⚙️ Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| LOT_SIZE | 50 | Contracts per lot |
| LOTS_PER_TRADE | 2 | Number of lots to trade |
| STOPLOSS_PCT | 0.50 | Stop loss percentage |
| START_TIME | 10:00 | Market entry start time |
| END_ENTRY_TIME | 14:45 | Last entry time |
| FORCE_EXIT_TIME | 14:59 | Hard exit time |
| MAX_LOSS | -37000 | Max loss before kill switch |

## 🛡️ Risk Management

### Built-in Safety Features
1. **Stop Loss Orders**: Automatically placed at 0.50% above entry price
2. **Time-based Exit**: All positions closed at 2:59 PM (EOD)
3. **Kill Switch**: Closes all positions if loss exceeds ₹-37,000
4. **Quantity Control**: Fixed position size prevents over-leverage

### Important Notes
⚠️ **This strategy involves significant risk. Use only with:**
- Adequate capital allocation
- Proper risk management
- Thorough backtesting before live trading
- Real-time monitoring of open positions

## 📊 How Stop Loss Works

```
Entry Price: ₹100.00
Stop Loss %: 0.50%
SL Trigger Price: ₹100.50

If option price rises to ₹100.50, position exits automatically
```

## 🔄 Real-time Monitoring

The strategy monitors:
- **Open Positions**: All active short positions
- **Daily P&L**: Real-time profit/loss
- **Order Status**: Entry, SL, and exit order fills
- **Risk Metrics**: Current loss vs MAX_LOSS limit

## 🐛 Troubleshooting

### "order_api is not initialized"
- Ensure API credentials are set in `config.py`
- Verify Upstox connection is active

### "CSV file not found"
- Check that `nifty_options.csv` and `nifty_spot.csv` exist in project directory
- Verify file paths and naming

### "No trades generated"
- Check market hours (10:00 - 14:59)
- Verify data contains options at required strikes
- Check time column format (must be HH:MM)

## 📝 API Integration Notes

Uses **Upstox API v2** with:
- Instrument tokens from Upstox master data
- Intraday (I) product type for options trading
- Market orders for quick execution
- SL-M (Stop Loss Market) orders for exits

## 📧 Support & Questions

For issues or questions:
1. Check [Upstox API Documentation](https://upstox.com/developer/documentation)
2. Review `DATA_FORMAT.md` for data specifications
3. Check trade_log.csv for past execution details

## 📜 License

This code is provided as-is for educational and trading purposes. Use at your own risk.

## ✅ Checklist Before Going Live

- [ ] API credentials configured in `config.py`
- [ ] CSV files (options & spot) prepared and validated
- [ ] Backtested with historical data
- [ ] Risk parameters reviewed and adjusted
- [ ] Adequate capital available
- [ ] Order monitoring setup active
- [ ] Kill switch limits verified
- [ ] Trade logging directory writable

---

**Author**: Hetvi Magia  
**Created**: Feb 6, 2026  
**Last Updated**: Feb 11, 2026
