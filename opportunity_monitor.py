import json
import time
from web3 import Web3
import os
import requests

# --- Configuração ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

w3 = Web3(Web3.HTTPProvider("https://base-mainnet.g.alchemy.com/v2/akWmmJe92KBl0WdKklCYXx1UW5msrmv0"))

# --- Endereços e ABIs ---
DEXS = {
    "Uniswap V3": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
    "SushiSwap V3": "0x57713f7716e0b0f65ec116912f834e49805480d2",
    "Aerodrome": "0xcdac0d6c6c59727a65f871236188350531885c43",
}

TOKENS = {
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

ERC20_ABI = json.loads("""[{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]""")
UNISWAP_V3_POOL_ABI = json.loads("""[{"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"},{"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]""")
AERODROME_POOL_ABI = json.loads("""[{"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"},{"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]""")

# --- Funções de Obtenção de Preços ---
def get_token_decimals(token_address):
    token_contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=ERC20_ABI)
    return token_contract.functions.decimals().call()

def get_uniswap_v3_price(pool_address, token_in_address, token_out_address):
    pool_contract = w3.eth.contract(address=w3.to_checksum_address(pool_address), abi=UNISWAP_V3_POOL_ABI)
    slot0 = pool_contract.functions.slot0().call()
    sqrt_price_x96 = slot0[0]
    token0_address = pool_contract.functions.token0().call()
    token0_decimals = get_token_decimals(token0_address)
    token1_decimals = get_token_decimals(w3.to_checksum_address(token_out_address))
    price = (sqrt_price_x96 / 2**96)**2
    if token_in_address.lower() == token0_address.lower():
        price = price / (10**(token1_decimals - token0_decimals))
    else:
        price = 1 / price
        price = price / (10**(token0_decimals - token1_decimals))
    return price

def get_aerodrome_price(pool_address, token_in_address, token_out_address):
    pool_contract = w3.eth.contract(address=w3.to_checksum_address(pool_address), abi=AERODROME_POOL_ABI)
    reserves = pool_contract.functions.getReserves().call()
    reserve0, reserve1 = reserves[0], reserves[1]
    token0_address = pool_contract.functions.token0().call()
    token0_decimals = get_token_decimals(token0_address)
    token1_decimals = get_token_decimals(w3.to_checksum_address(token_out_address))
    if token_in_address.lower() == token0_address.lower():
        price = (reserve1 / 10**token1_decimals) / (reserve0 / 10**token0_decimals)
    else:
        price = (reserve0 / 10**token0_decimals) / (reserve1 / 10**token1_decimals)
    return price

PRICE_FUNCTIONS = {
    "Uniswap V3": get_uniswap_v3_price,
    "SushiSwap V3": get_uniswap_v3_price, # Using the same logic as Uniswap V3
    "Aerodrome": get_aerodrome_price,
}

# --- Função de Notificação ---
def send_telegram_notification(message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error sending Telegram notification: {e}")

# --- Loop Principal ---
if __name__ == "__main__":
    print("Starting arbitrage opportunity monitor...")
    send_telegram_notification("Arbitrage bot started!")
    while True:
        for dex1_name, dex1_address in DEXS.items():
            for dex2_name, dex2_address in DEXS.items():
                if dex1_name == dex2_name:
                    continue

                for token1_symbol, token1_address in TOKENS.items():
                    for token2_symbol, token2_address in TOKENS.items():
                        if token1_symbol == token2_symbol:
                            continue

                        try:
                            price1 = PRICE_FUNCTIONS[dex1_name](dex1_address, token1_address, token2_address)
                            time.sleep(1) # Avoid rate limiting
                            price2 = PRICE_FUNCTIONS[dex2_name](dex2_address, token1_address, token2_address)
                            time.sleep(1)

                            if price1 is not None and price2 is not None and price1 > 0 and price2 > 0:
                                profit = (price2 / price1) - 1

                                if profit > 0.001: # 0.1% profit threshold
                                    message = (
                                        f"Arbitrage Opportunity Found!\n"
                                        f"  - Buy {token1_symbol} on {dex1_name} at {price1:.6f} {token2_symbol}\n"
                                        f"  - Sell {token1_symbol} on {dex2_name} at {price2:.6f} {token2_symbol}\n"
                                        f"  - Estimated Profit: {profit * 100:.2f}%"
                                    )
                                    print(message)
                                    send_telegram_notification(message)
                        except Exception as e:
                            # print(f"Error processing pair {token1_symbol}/{token2_symbol} on {dex1_name}/{dex2_name}: {e}")
                            pass

        print("Finished a cycle. Waiting for the next one...")
        time.sleep(300) # Wait 5 minutes before the next cycle

