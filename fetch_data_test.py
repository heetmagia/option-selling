import upstox_client
print("Upstox SDK imported successfully")
from upstox_client.api.market_quote_api import MarketQuoteApi
print("MarketQuoteApi available")
print(dir(MarketQuoteApi))

import upstox_client
from upstox_client.configuration import Configuration
from upstox_client.api_client import ApiClient
from upstox_client.api.market_quote_api import MarketQuoteApi

# Configure access token
config = Configuration()
config.access_token = "tc9y4ys42r"

client = ApiClient(config)
quote_api = MarketQuoteApi(client)

response = quote_api.get_market_quote(
    instruments=["NSE_INDEX|Nifty 50"]
)

nifty_spot = response.data["NSE_INDEX|Nifty 50"].last_price
print("NIFTY SPOT:", nifty_spot)

