#!/usr/bin/env python3
"""
Flash Loans Arbitrage Bot - v2 com Execução Automática
"""

import json
import time
import logging
import os
import sys
from datetime import datetime
from web3 import Web3
import requests
from flask import Flask, jsonify
import threading

# Importar o executor
from trade_executor import TradeExecutor

# --- Configuração de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/arbitrage_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Configuração Principal ---
class Config:
    # Conexão
    ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY", "akWmmJe92KBl0WdKklCYXx1UW5msrmv0")
    WEB3_PROVIDER_URL = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    
    # Chaves e Contratos
    PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
    CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS") # Precisa ser definido no .env
    
    # Notificações
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    
    # Parâmetros de Trade
    MIN_PROFIT_THRESHOLD = 0.005  # 0.5%
    FLASH_LOAN_AMOUNT_WETH = 1 * (10**18) # 1 WETH
    FLASH_LOAN_AMOUNT_USDC = 1000 * (10**6) # 1000 USDC
    MAX_GAS_PRICE_GWEI = 50
    SLIPPAGE_BPS = 100 # 1%

    # Timings
    API_CALL_DELAY = 2  # Segundos
    CYCLE_DELAY = 180   # 3 Minutos

# --- ABIs e Endereços ---
# (O ABI do FlashArbitrage será carregado de um arquivo)
with open("contracts/FlashArbitrage.json", "r") as f:
    FLASH_ARBITRAGE_ABI = json.load(f)["abi"]

DEXS = {
    "Uniswap V3": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
    "SushiSwap V3": "0x57713f7716e0b0f65ec116912f834e49805480d2",
    "Aerodrome": "0xcdac0d6c6c59727a65f871236188350531885c43",
}

TOKENS = {
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

# ... (O restante das classes RateLimiter, TelegramNotifier, etc. permanece o mesmo)

class PriceMonitor:
    def __init__(self):
        # ... (inicialização do rate_limiter, telegram, stats)
        self.w3 = Web3(Web3.HTTPProvider(Config.WEB3_PROVIDER_URL))
        self.trade_executor = None
        if Config.PRIVATE_KEY and Config.CONTRACT_ADDRESS:
            self.trade_executor = TradeExecutor(
                web3_provider_url=Config.WEB3_PROVIDER_URL,
                private_key=Config.PRIVATE_KEY,
                contract_address=Config.CONTRACT_ADDRESS,
                contract_abi=FLASH_ARBITRAGE_ABI
            )
            logger.info("Executor de trades inicializado.")
        else:
            logger.warning("Executor de trades não inicializado. Rodando em modo SOMENTE MONITOR.")

    # ... (funções de get_price permanecem as mesmas)

    def check_arbitrage_opportunity(self):
        for dex1_name, dex1_address in DEXS.items():
            for dex2_name, dex2_address in DEXS.items():
                if dex1_name == dex2_name:
                    continue
                
                for token1_symbol, token1_address in TOKENS.items():
                    for token2_symbol, token2_address in TOKENS.items():
                        if token1_symbol == token2_symbol:
                            continue
                        
                        try:
                            price1 = self.get_price(dex1_name, dex1_address, token1_address, token2_address)
                            price2 = self.get_price(dex2_name, dex2_address, token1_address, token2_address)
                            
                            if price1 and price2 and price1 > 0 and price2 > 0:
                                profit = (price2 / price1) - 1
                                
                                if profit > Config.MIN_PROFIT_THRESHOLD:
                                    self.stats["opportunities_found"] += 1
                                    logger.info(f"Oportunidade encontrada: {profit*100:.2f}% - {token1_symbol}/{token2_symbol}")

                                    # Se o executor estiver configurado, executa o trade
                                    if self.trade_executor:
                                        amount_in = Config.FLASH_LOAN_AMOUNT_WETH if token1_symbol == 'WETH' else Config.FLASH_LOAN_AMOUNT_USDC
                                        
                                        opportunity = {
                                            'tokenA': self.w3.to_checksum_address(token1_address),
                                            'tokenB': self.w3.to_checksum_address(token2_address),
                                            'dexBuy': self.w3.to_checksum_address(dex1_address),
                                            'dexSell': self.w3.to_checksum_address(dex2_address),
                                            'amountIn': amount_in,
                                            'minProfitBps': int(Config.MIN_PROFIT_THRESHOLD * 10000),
                                            'deadline': int(time.time()) + 300 # 5 minutos
                                        }

                                        logger.info(f"Executando trade para oportunidade: {opportunity}")
                                        tx_hash = self.trade_executor.execute_trade(opportunity)

                                        if tx_hash:
                                            message = (
                                                f"🚀 *Trade Executado!*\n\n"
                                                f"💰 *Lucro Estimado:* {profit * 100:.2f}%\n"
                                                f"🔗 *Tx Hash:* `{tx_hash}`\n"
                                                f"📈 *Comprar em:* {dex1_name}\n"
                                                f"📉 *Vender em:* {dex2_name}"
                                            )
                                            self.telegram.send_message(message)
                                        else:
                                            self.telegram.send_message(f"❌ *Falha ao executar trade* para oportunidade com {profit*100:.2f}% de lucro.")
                                    else:
                                        # Apenas notifica se não houver executor
                                        message = (
                                            f"🚨 *Oportunidade de Arbitragem (SOMENTE MONITOR)!*\n\n"
                                            f"💰 *Lucro Estimado:* {profit * 100:.2f}%\n"
                                            f"📈 *Comprar {token1_symbol} em:* {dex1_name} por {price1:.6f}\n"
                                            f"📉 *Vender {token1_symbol} em:* {dex2_name} por {price2:.6f}"
                                        )
                                        self.telegram.send_message(message)

                        except Exception as e:
                            self.stats["errors"] += 1
                            logger.error(f"Erro ao processar {token1_symbol}/{token2_symbol}: {e}")

    # ... (o resto do arquivo, como start(), run_flask(), etc. permanece o mesmo)

# --- Ponto de Entrada ---
if __name__ == "__main__":
    if not Config.PRIVATE_KEY or not Config.CONTRACT_ADDRESS:
        logger.error("PRIVATE_KEY e CONTRACT_ADDRESS devem ser definidos no ambiente para execução de trades.")
    
    # ... (resto da inicialização)
    monitor = PriceMonitor()
    monitor.start()

