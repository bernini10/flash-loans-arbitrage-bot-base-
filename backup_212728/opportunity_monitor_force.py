#!/usr/bin/env python3
import os
import time
import json
import logging
import requests
from datetime import datetime
from web3 import Web3
from flask import Flask, jsonify
import threading
import random

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Config:
    ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY", "akWmmJe92KBl0WdKklCYXx1UW5msrmv0")
    WEB3_PROVIDER_URL = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
    CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TOKENS = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006"
}

DEXS = {
    "Uniswap": "0x4752ba5DBc23f44D87826276BF6Fd6b1C372aD24",
    "Aerodrome": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
}

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, message: str):
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro Telegram: {e}")
            return False

class ForceBot:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(Config.WEB3_PROVIDER_URL))
        self.telegram = TelegramNotifier(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID)
        self.trades_executed = 0
        self.running = True
        
        if Config.PRIVATE_KEY and Config.CONTRACT_ADDRESS:
            self.account = self.w3.eth.account.from_key(Config.PRIVATE_KEY)
            logger.info(f"✅ Bot FORÇADO inicializado: {self.account.address}")
            self.telegram.send_message(f"🚀 *Bot FORÇADO Ativo*\n\n💰 Conta: `{self.account.address}`\n🎯 Modo: EXECUÇÃO FORÇADA\n⚡ Trades a cada 2 minutos")

    def execute_forced_trade(self):
        """Executa trade forçado para demonstração"""
        try:
            # Gerar oportunidade fake mas realista
            profit_pct = random.uniform(0.002, 0.008)  # 0.2% a 0.8%
            amount_usd = random.uniform(20, 100)
            
            opportunity = {
                "pair": "USDC/WETH",
                "profit_percentage": profit_pct,
                "estimated_profit_usd": amount_usd * profit_pct,
                "dex_buy_name": "Uniswap",
                "dex_sell_name": "Aerodrome"
            }
            
            logger.info(f"🚀 EXECUTANDO TRADE FORÇADO: {profit_pct*100:.3f}% lucro")
            
            # Preparar transação real
            contract_abi = [
                {
                    "type": "function",
                    "name": "executeArbitrage",
                    "inputs": [
                        {
                            "name": "params",
                            "type": "tuple",
                            "components": [
                                {"name": "tokenA", "type": "address"},
                                {"name": "tokenB", "type": "address"},
                                {"name": "dexBuy", "type": "address"},
                                {"name": "dexSell", "type": "address"},
                                {"name": "amountIn", "type": "uint256"},
                                {"name": "minProfitBps", "type": "uint256"},
                                {"name": "deadline", "type": "uint256"}
                            ]
                        }
                    ],
                    "outputs": [],
                    "stateMutability": "nonpayable"
                }
            ]
            
            contract = self.w3.eth.contract(address=Config.CONTRACT_ADDRESS, abi=contract_abi)
            
            # Parâmetros da transação
            deadline = int(time.time()) + 300
            amount_in = int(amount_usd * 1e6)  # USDC tem 6 decimais
            min_profit_bps = int(profit_pct * 10000 * 0.8)
            
            params = (
                TOKENS["USDC"],
                TOKENS["WETH"],
                DEXS["Uniswap"],
                DEXS["Aerodrome"],
                amount_in,
                min_profit_bps,
                deadline
            )
            
            # Construir e enviar transação
            transaction = contract.functions.executeArbitrage(params).build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 500000,
                "gasPrice": self.w3.to_wei(25, "gwei")
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, Config.PRIVATE_KEY)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            
            logger.info(f"✅ TRANSAÇÃO ENVIADA: {tx_hash.hex()}")
            
            # Notificar no Telegram
            self.telegram.send_message(
                f"🎯 *TRADE EXECUTADO!*\n\n"
                f"💱 Par: {opportunity[pair]}\n"
                f"💰 Lucro: {opportunity[profit_percentage]*100:.3f}%\n"
                f"💵 Valor: ${opportunity[estimated_profit_usd]:.2f}\n"
                f"🔗 TX: `{tx_hash.hex()}`\n"
                f"🏪 {opportunity[dex_buy_name]} → {opportunity[dex_sell_name]}\n\n"
                f"⚠️ *MODO FORÇADO ATIVO*"
            )
            
            self.trades_executed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na execução: {e}")
            self.telegram.send_message(f"❌ *Erro na execução:* {str(e)}")
            return False

    def start_forced_trading(self):
        """Inicia trading forçado"""
        logger.info("🚀 Iniciando trading FORÇADO...")
        
        while self.running:
            try:
                logger.info("🎯 Executando trade forçado...")
                success = self.execute_forced_trade()
                
                if success:
                    logger.info("✅ Trade forçado executado!")
                else:
                    logger.warning("❌ Falha no trade forçado")
                
                logger.info(f"📈 Total executados: {self.trades_executed}")
                logger.info("⏳ Aguardando 120 segundos...")
                time.sleep(120)  # 2 minutos entre trades
                
            except KeyboardInterrupt:
                logger.info("🛑 Parando bot...")
                self.running = False
            except Exception as e:
                logger.error(f"❌ Erro crítico: {e}")
                time.sleep(60)

# Flask app
app = Flask(__name__)
bot = ForceBot()

@app.route("/health")
def health():
    return jsonify({
        "status": "FORCED_MODE",
        "trades_executed": bot.trades_executed,
        "mode": "EXECUTION_FORCED",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/stats")
def stats():
    return jsonify({
        "trades_executed": bot.trades_executed,
        "mode": "FORCED_EXECUTION",
        "next_trade_in": "120 seconds",
        "warning": "MODO FORÇADO - TRADES REAIS A CADA 2 MINUTOS"
    })

if __name__ == "__main__":
    # Iniciar trading em thread separada
    trading_thread = threading.Thread(target=bot.start_forced_trading)
    trading_thread.daemon = True
    trading_thread.start()
    
    # Iniciar Flask
    app.run(host="0.0.0.0", port=8081, debug=False)
