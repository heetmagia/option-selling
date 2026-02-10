# Data Format Specification

This document outlines the required CSV format for running the NIFTY 15-Min Option Selling Strategy.

## 1. nifty_options.csv - Options Chain Data

### Required Columns

| Column | Type | Format | Example | Notes |
|--------|------|--------|---------|-------|
| datetime | datetime | YYYY-MM-DD HH:MM:SS | 2025-02-10 10:00:00 | Must be aligned to 5-min or 15-min candles |
| expiry | date | YYYY-MM-DD | 2025-02-13 | Next weekly expiry date |
| strike | float | Numeric | 23000.0 | Strike price (typically 100-point intervals) |
| option_type | string | "CE" or "PE" | CE | Call or Put option |
| open | float | Numeric | 120.50 | Opening price |
| high | float | Numeric | 125.75 | High of candle |
| low | float | Numeric | 118.25 | Low of candle |
| close | float | Numeric | 123.45 | Closing/LTP price |
| volume | integer | Numeric | 15000 | Volume in contracts |
| instrument_token | string | Numeric | "12345678" | Unique Upstox instrument identifier |

### Sample Data (nifty_options.csv)

```csv
datetime,expiry,strike,option_type,open,high,low,close,volume,instrument_token
2025-02-10 10:00:00,2025-02-13,23000,CE,125.50,127.75,124.25,126.50,12000,123456789
2025-02-10 10:00:00,2025-02-13,22700,PE,98.25,101.50,97.00,99.75,8500,987654321
2025-02-10 10:15:00,2025-02-13,23000,CE,126.50,128.50,125.75,127.25,15000,123456789
2025-02-10 10:15:00,2025-02-13,22700,PE,99.75,102.25,98.50,100.50,9200,987654321
```

### Data Source Options

**Option 1: Upstox Historical Data**
- Download from Upstox historical data portal
- Ensure 15-min candle data is selected
- Include all columns mentioned above

**Option 2: Build from Upstox API**
```python
# Pseudo-code to fetch data
from upstox_client import UpstoxClient

client = UpstoxClient(api_key, client_id)
options_chain = client.get_option_chain(
    underlying="NIFTY",
    expiry="2025-02-13",
    interval="15min"
)
```

**Option 3: Use Existing Provider**
- Zerodha (Kite API)
- Alice Blue
- ICICI Direct

---

## 2. nifty_spot.csv - Spot Price Data

### Required Columns

| Column | Type | Format | Example | Notes |
|--------|------|--------|---------|-------|
| datetime | datetime | YYYY-MM-DD HH:MM:SS | 2025-02-10 10:00:00 | Must align with options data |
| open | float | Numeric | 22950.50 | Opening price |
| high | float | Numeric | 23100.75 | High of candle |
| low | float | Numeric | 22850.25 | Low of candle |
| close | float | Numeric | 23050.00 | Closing price (used for strike calculation) |
| volume | integer | Numeric | 120000000 | Volume in rupees or contracts |

### Sample Data (nifty_spot.csv)

```csv
datetime,open,high,low,close,volume
2025-02-10 10:00:00,22950.50,23100.75,22850.25,23050.00,120000000
2025-02-10 10:15:00,23050.00,23125.50,22975.00,23100.00,125000000
2025-02-10 10:30:00,23100.00,23150.00,23000.00,23080.00,118000000
2025-02-10 10:45:00,23080.00,23200.00,23050.00,23180.00,130000000
```

### Strike Calculation Logic

Based on spot price at each 15-min mark:

```
CE Strike = ROUND((Spot + 300) / 50) * 50
PE Strike = ROUND((Spot - 300) / 50) * 50

Example:
Spot Price: 23,050
CE Strike: ROUND((23050 + 300) / 50) * 50 = ROUND(467) * 50 = 23,500
PE Strike: ROUND((23050 - 300) / 50) * 50 = ROUND(455) * 50 = 22,750
```

---

## 3. trade_log.csv - Generated After Strategy Execution

### Columns

| Column | Type | Description |
|--------|------|-------------|
| date | date | Trading date |
| time | datetime | Entry timestamp |
| strike | float | Strike price entered |
| type | string | "CE" or "PE" |
| entry_price | float | Average fill price |
| qty | integer | Quantity filled |
| entry_order_id | string | Upstox order ID |
| sl_order_id | string | Stop loss order ID |

### Sample Output (trade_log.csv)

```csv
date,time,strike,type,entry_price,qty,entry_order_id,sl_order_id
2025-02-10,2025-02-10 10:00:00,23050.0,CE,126.50,100,ORD20250210000001,ORD20250210000002
2025-02-10,2025-02-10 10:00:00,22750.0,PE,99.75,100,ORD20250210000003,ORD20250210000004
2025-02-10,2025-02-10 10:15:00,23100.0,CE,128.25,100,ORD20250210000005,ORD20250210000006
2025-02-10,2025-02-10 10:15:00,22800.0,PE,101.50,100,ORD20250210000007,ORD20250210000008
```

---

## Data Validation Checklist

### Before running the strategy, verify:

- [ ] Both CSV files exist in the project directory
- [ ] All required columns are present
- [ ] datetime format is consistent (YYYY-MM-DD HH:MM:SS)
- [ ] No missing values in critical columns (datetime, strike, close, option_type)
- [ ] Option data includes both CE and PE for all required strikes
- [ ] Data covers full trading hours (9:15 AM - 3:30 PM IST)
- [ ] Spot price and options data timestamps match
- [ ] Strike prices are in 100/50-point intervals
- [ ] Volume data is realistic (not zero on valid 15-min bars)
- [ ] instrument_token values are not empty

### Python Validation Script

```python
import pandas as pd

def validate_data():
    options = pd.read_csv('nifty_options.csv', parse_dates=['datetime', 'expiry'])
    spot = pd.read_csv('nifty_spot.csv', parse_dates=['datetime'])
    
    print("Options Data Shape:", options.shape)
    print("Spot Data Shape:", spot.shape)
    
    # Check for null values
    print("\nNull Values in Options:")
    print(options.isnull().sum())
    
    print("\nNull Values in Spot:")
    print(spot.isnull().sum())
    
    # Check date range
    print(f"\nOptions Date Range: {options['datetime'].min()} to {options['datetime'].max()}")
    print(f"Spot Date Range: {spot['datetime'].min()} to {spot['datetime'].max()}")
    
    # Check unique strikes
    print(f"\nUnique Strikes: {options['strike'].nunique()}")
    print(f"Unique Option Types: {options['option_type'].unique()}")
    
    return options, spot

options_df, spot_df = validate_data()
```

---

## Common Data Issues & Solutions

### Issue: "CSV file has different number of rows"
- **Cause**: Data gaps (missing 15-min candles)
- **Solution**: Forward-fill missing timestamps and interpolate prices

### Issue: "Strike prices don't match calculated values"
- **Cause**: Strike rounding or spot data misalignment
- **Solution**: Re-calculate strikes using exact spot price at each 15-min mark

### Issue: "instrument_token is missing"
- **Cause**: Data source doesn't include Upstox tokens
- **Solution**: Map strike + option_type to tokens using Upstox master data

### Issue: "No options found for calculated strikes"
- **Cause**: Strike calculation results in non-existent strikes
- **Solution**: Verify spot data accuracy; use nearest available strike

---

## Updating Data

### For Backtesting
- Use historical data (previous trading days)
- Ensure data is complete and accurate

### For Live Trading
- Data should be real-time or 15-min candle updates
- Integrate with Upstox WebSocket for live updates
- Refresh spot price before each entry check

---

**Last Updated**: Feb 11, 2026
