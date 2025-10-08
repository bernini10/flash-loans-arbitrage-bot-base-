#!/usr/bin/env python3
import os
import time
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from web3 import Web3
from flask import Flask, jsonify
import threading

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/arbitrage_aggressive.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurações
class Config:
    ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY", "akWmmJe92KBl0WdKklCYXx1UW5msrmv0")
    WEB3_PROVIDER_URL = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
    CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    MIN_PROFIT_THRESHOLD = float(os.environ.get("MIN_PROFIT_THRESHOLD", "0.001"))  # 0.1%
    MAX_GAS_PRICE_GWEI = int(os.environ.get("MAX_GAS_PRICE", "30"))
    CYCLE_DELAY = int(os.environ.get("CYCLE_DELAY", "60"))  # 1 minuto

# Tokens principais na Base
TOKENS = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "WETH": "0x4200000000000000000000000000000000000006", 
    "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
    "USDT": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2"
}

# DEXs na Base
DEXS = {
    "Uniswap": "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24",
    "Aerodrome": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43",
    "SushiSwap": "0x4C5D5234f232BD2D76B96aA33F5AE4FCF0E4BFaB"
}

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, message: str):
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False

class ArbitrageBot:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(Config.WEB3_PROVIDER_URL))
        self.telegram = TelegramNotifier(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID)
        self.opportunities_found = 0
        self.trades_executed = 0
        self.running = True
        
        # Inicializar executor se chaves estão disponíveis
        if Config.PRIVATE_KEY and Config.CONTRACT_ADDRESS:
            self.account = self.w3.eth.account.from_key(Config.PRIVATE_KEY)
            logger.info(f"✅ Executor inicializado para: {self.account.address}")
            self.telegram.send_message(f"🚀 *Bot Agressivo Iniciado*\n\n💰 Conta: `{self.account.address}`\n🎯 Threshold: {Config.MIN_PROFIT_THRESHOLD*100:.3f}%\n⚡ Ciclo: {Config.CYCLE_DELAY}s")
        else:
            logger.warning("⚠️ Modo somente monitor - chaves não configuradas")

    def get_token_price_coingecko(self, token_address: str) -> float:
        """Busca preço via CoinGecko"""
        try:
            # Mapeamento de endereços para IDs do CoinGecko
            token_ids = {
                TOKENS["USDC"]: "usd-coin",
                TOKENS["WETH"]: "ethereum", 
                TOKENS["DAI"]: "dai",
                TOKENS["USDT"]: "tether"
            }
            
            token_id = token_ids.get(token_address.lower())
            if not token_id:
                return 0.0
                
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={token_id}&vs_currencies=usd"
            response = requests.get(url, timeout=5)
            data = response.json()
            return float(data[token_id]["usd"])
        except:
            return 0.0

    def simulate_arbitrage_opportunity(self) -> List[Dict]:
        """Simula oportunidades de arbitragem com preços reais"""
        opportunities = []
        
        try:
            # Buscar preços reais
            usdc_price = self.get_token_price_coingecko(TOKENS["USDC"])
            eth_price = self.get_token_price_coingecko(TOKENS["WETH"])
            
            if usdc_price > 0 and eth_price > 0:
                # Simular pequenas diferenças de preço entre DEXs
                import random
                
                for dex1 in ["Uniswap", "Aerodrome"]:
                    for dex2 in ["SushiSwap", "Aerodrome"]:
                        if dex1 != dex2:
                            # Simular diferença de 0.1% a 0.5%
                            price_diff = random.uniform(0.001, 0.005)
                            
                            opportunity = {
                                "token_in": TOKENS["USDC"],
                                "token_out": TOKENS["WETH"], 
                                "dex_buy": DEXS[dex1],
                                "dex_sell": DEXS[dex2],
                                "amount_in": int(50 * 1e6),  # 50 USDC
                                "profit_percentage": price_diff,
                                "estimated_profit_usd": 50 * price_diff,
                                "gas_cost_usd": 2.0,
                                "net_profit_usd": (50 * price_diff) - 2.0,
                                "pair": "USDC/WETH",
                                "dex_buy_name": dex1,
                                "dex_sell_name": dex2
                            }
                            
                            # Só adicionar se for rentável após gas
                            if opportunity["net_profit_usd"] > 0 and price_diff >= Config.MIN_PROFIT_THRESHOLD:
                                opportunities.append(opportunity)
                                
        except Exception as e:
            logger.error(f"Erro ao simular oportunidades: {e}")
            
        return opportunities

    def execute_trade(self, opportunity: Dict) -> bool:
        """Executa trade real na blockchain"""
        try:
            if not hasattr(self, "account"):
                logger.warning("❌ Executor não inicializado")
                return False
                
            logger.info(f"🚀 Executando trade: {opportunity['pair']} - Lucro: {opportunity[profit_percentage]*100:.3f}%")
            
            # Preparar transação para o contrato
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
            
            contract = self.w3.eth.contract(
                address=Config.CONTRACT_ADDRESS,
                abi=contract_abi
            )
            
            # Parâmetros da transação
            deadline = int(time.time()) + 300  # 5 minutos
            min_profit_bps = int(opportunity["profit_percentage"] * 10000 * 0.8)  # 80% do lucro esperado
            
            params = (
                opportunity["token_in"],
                opportunity["token_out"],
                opportunity["dex_buy"],
                opportunity["dex_sell"],
                opportunity["amount_in"],
                min_profit_bps,
                deadline
            )
            
            # Construir transação
            transaction = contract.functions.executeArbitrage(params).build_transaction({
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "gas": 500000,
                "gasPrice": self.w3.to_wei(Config.MAX_GAS_PRICE_GWEI, "gwei")
            })
            
            # Assinar e enviar
            signed_txn = self.w3.eth.account.sign_transaction(transaction, Config.PRIVATE_KEY)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            
            logger.info(f"✅ Transação enviada: {tx_hash.hex()}")
            
            # Notificar sucesso
            self.telegram.send_message(
                f"🎯 *Trade Executado!*\n\n"
                f"💱 Par: {opportunity['pair']}\n"
                f"💰 Lucro: {opportunity[profit_percentage]*100:.3f}%\n"
                f"💵 Valor: ${opportunity[estimated_profit_usd]:.2f}\n"
                f"🔗 TX: `{tx_hash.hex()}`\n"
                f"🏪 {opportunity[dex_buy_name]} → {opportunity[dex_sell_name]}"
            )
            
            self.trades_executed += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao executar trade: {e}")
            self.telegram.send_message(f"❌ *Erro na execução:* {str(e)}")
            return False

    def run_cycle(self):
        """Executa um ciclo de monitoramento"""
        try:
            logger.info("🔍 Iniciando ciclo agressivo...")
            
            opportunities = self.simulate_arbitrage_opportunity()
            self.opportunities_found += len(opportunities)
            
            if opportunities:
                logger.info(f"🎯 {len(opportunities)} oportunidades encontradas!")
                
                # Executar a melhor oportunidade
                best_opportunity = max(opportunities, key=lambda x: x["net_profit_usd"])
                
                if best_opportunity["net_profit_usd"] > 0:
                    success = self.execute_trade(best_opportunity)
                    if success:
                        logger.info("✅ Trade executado com sucesso!")
                    else:
                        logger.warning("❌ Falha na execução do trade")
                        
            else:
                logger.info("📊 Nenhuma oportunidade rentável encontrada")
                
            logger.info(f"📈 Stats: {self.opportunities_found} encontradas, {self.trades_executed} executadas")
            
        except Exception as e:
            logger.error(f"❌ Erro no ciclo: {e}")

    def start_monitoring(self):
        """Inicia monitoramento contínuo"""
        logger.info("🚀 Iniciando bot agressivo...")
        
        while self.running:
            try:
                self.run_cycle()
                logger.info(f"⏳ Aguardando {Config.CYCLE_DELAY} segundos...")
                time.sleep(Config.CYCLE_DELAY)
            except KeyboardInterrupt:
                logger.info("🛑 Parando bot...")
                self.running = False
            except Exception as e:
                logger.error(f"❌ Erro crítico: {e}")
                time.sleep(30)

# Flask app para health check
app = Flask(__name__)
bot = ArbitrageBot()

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "opportunities_found": bot.opportunities_found,
        "trades_executed": bot.trades_executed,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/stats")
def stats():
    return jsonify({
        "opportunities_found": bot.opportunities_found,
        "trades_executed": bot.trades_executed,
        "success_rate": bot.trades_executed / max(bot.opportunities_found, 1) * 100,
        "config": {
            "min_profit_threshold": Config.MIN_PROFIT_THRESHOLD,
            "cycle_delay": Config.CYCLE_DELAY,
            "max_gas_price": Config.MAX_GAS_PRICE_GWEI
        }
    })

if __name__ == "__main__":
    # Iniciar monitoramento em thread separada
    monitoring_thread = threading.Thread(target=bot.start_monitoring)
    monitoring_thread.daemon = True
    monitoring_thread.start()
    
    # Iniciar Flask app
    app.run(host="0.0.0.0", port=8081, debug=False)
