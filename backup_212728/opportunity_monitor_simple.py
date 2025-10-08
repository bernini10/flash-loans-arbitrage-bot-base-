#!/usr/bin/env python3
"""
Flash Loans Arbitrage Bot - Monitor de Oportunidades
Versão melhorada com rate limiting, health check e logging
"""

import json
import time
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Tuple
from web3 import Web3
import requests
from flask import Flask, jsonify
import threading

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/arbitrage_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuração
class Config:
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY", "akWmmJe92KBl0WdKklCYXx1UW5msrmv0")
    PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
    
    # Rate limiting
    API_CALL_DELAY = 2  # segundos entre chamadas
    CYCLE_DELAY = 300   # 5 minutos entre ciclos
    MAX_RETRIES = 3
    
    # Thresholds
    MIN_PROFIT_THRESHOLD = 0.005  # 0.5%
    MAX_GAS_PRICE = 50  # gwei

# Inicializar Web3
w3 = Web3(Web3.HTTPProvider(f"https://base-mainnet.g.alchemy.com/v2/{Config.ALCHEMY_API_KEY}"))

# Configurações de contratos
DEXS = {
    "Uniswap V3": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
    "SushiSwap V3": "0x57713f7716e0b0f65ec116912f834e49805480d2",
    "Aerodrome": "0xcdac0d6c6c59727a65f871236188350531885c43",
}

TOKENS = {
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

# ABIs
ERC20_ABI = [{"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]

UNISWAP_V3_POOL_ABI = [
    {"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"}],"stateMutability":"view","type":"function"},
    {"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
]

AERODROME_POOL_ABI = [
    {"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"}],"stateMutability":"view","type":"function"},
    {"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
]

class RateLimiter:
    def __init__(self, delay: float):
        self.delay = delay
        self.last_call = 0
    
    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_call = time.time()

class TelegramNotifier:
    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.rate_limiter = RateLimiter(1.0)  # 1 segundo entre mensagens
    
    def send_message(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram não configurado")
            return False
        
        self.rate_limiter.wait()
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False

class PriceMonitor:
    def __init__(self):
        self.rate_limiter = RateLimiter(Config.API_CALL_DELAY)
        self.telegram = TelegramNotifier()
        self.stats = {
            "cycles": 0,
            "opportunities_found": 0,
            "errors": 0,
            "last_update": datetime.now()
        }
    
    def get_token_decimals(self, token_address: str) -> Optional[int]:
        try:
            self.rate_limiter.wait()
            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(token_address), 
                abi=ERC20_ABI
            )
            return token_contract.functions.decimals().call()
        except Exception as e:
            logger.error(f"Erro ao obter decimais do token {token_address}: {e}")
            return None
    
    def get_uniswap_v3_price(self, pool_address: str, token_in: str, token_out: str) -> Optional[float]:
        try:
            self.rate_limiter.wait()
            pool_contract = w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=UNISWAP_V3_POOL_ABI
            )
            
            slot0 = pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            
            token0_address = pool_contract.functions.token0().call()
            token1_address = pool_contract.functions.token1().call()
            
            token0_decimals = self.get_token_decimals(token0_address)
            token1_decimals = self.get_token_decimals(token1_address)
            
            if token0_decimals is None or token1_decimals is None:
                return None
            
            price = (sqrt_price_x96 / 2**96)**2
            
            if token_in.lower() == token0_address.lower():
                price = price / (10**(token1_decimals - token0_decimals))
            else:
                price = 1 / price
                price = price / (10**(token0_decimals - token1_decimals))
            
            return price
            
        except Exception as e:
            logger.error(f"Erro ao obter preço Uniswap V3: {e}")
            return None
    
    def get_aerodrome_price(self, pool_address: str, token_in: str, token_out: str) -> Optional[float]:
        try:
            self.rate_limiter.wait()
            pool_contract = w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=AERODROME_POOL_ABI
            )
            
            reserves = pool_contract.functions.getReserves().call()
            reserve0, reserve1 = reserves[0], reserves[1]
            
            token0_address = pool_contract.functions.token0().call()
            
            token0_decimals = self.get_token_decimals(token0_address)
            token1_decimals = self.get_token_decimals(token_out)
            
            if token0_decimals is None or token1_decimals is None:
                return None
            
            if token_in.lower() == token0_address.lower():
                price = (reserve1 / 10**token1_decimals) / (reserve0 / 10**token0_decimals)
            else:
                price = (reserve0 / 10**token0_decimals) / (reserve1 / 10**token1_decimals)
            
            return price
            
        except Exception as e:
            logger.error(f"Erro ao obter preço Aerodrome: {e}")
            return None
    
    def get_price(self, dex_name: str, pool_address: str, token_in: str, token_out: str) -> Optional[float]:
        if dex_name in ["Uniswap V3", "SushiSwap V3"]:
            return self.get_uniswap_v3_price(pool_address, token_in, token_out)
        elif dex_name == "Aerodrome":
            return self.get_aerodrome_price(pool_address, token_in, token_out)
        return None
    
    def check_arbitrage_opportunity(self) -> None:
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
                                    
                                    message = (
                                        f"🚨 *Oportunidade de Arbitragem!*\n\n"
                                        f"💰 *Lucro Estimado:* {profit * 100:.2f}%\n"
                                        f"🔄 *Par:* {token1_symbol}/{token2_symbol}\n"
                                        f"📈 *Comprar em:* {dex1_name} por {price1:.6f}\n"
                                        f"📉 *Vender em:* {dex2_name} por {price2:.6f}\n"
                                        f"⏰ *Timestamp:* {datetime.now().strftime('%H:%M:%S')}"
                                    )
                                    
                                    logger.info(f"Oportunidade encontrada: {profit*100:.2f}% - {token1_symbol}/{token2_symbol}")
                                    self.telegram.send_message(message)
                        
                        except Exception as e:
                            self.stats["errors"] += 1
                            logger.error(f"Erro ao processar {token1_symbol}/{token2_symbol} em {dex1_name}/{dex2_name}: {e}")
    
    def run_monitoring_cycle(self) -> None:
        logger.info("Iniciando ciclo de monitoramento...")
        self.stats["cycles"] += 1
        self.stats["last_update"] = datetime.now()
        
        try:
            self.check_arbitrage_opportunity()
            logger.info(f"Ciclo {self.stats['cycles']} concluído")
        except Exception as e:
            logger.error(f"Erro no ciclo de monitoramento: {e}")
            self.stats["errors"] += 1
    
    def start(self) -> None:
        logger.info("🚀 Iniciando Flash Arbitrage Bot...")
        self.telegram.send_message("🤖 *Flash Arbitrage Bot iniciado!*\n\n✅ Monitoramento ativo")
        
        while True:
            try:
                self.run_monitoring_cycle()
                logger.info(f"Aguardando {Config.CYCLE_DELAY} segundos para próximo ciclo...")
                time.sleep(Config.CYCLE_DELAY)
            except KeyboardInterrupt:
                logger.info("Bot interrompido pelo usuário")
                self.telegram.send_message("🛑 *Bot parado pelo usuário*")
                break
            except Exception as e:
                logger.error(f"Erro crítico: {e}")
                self.telegram.send_message(f"❌ *Erro crítico:* {str(e)}")
                time.sleep(60)  # Aguardar 1 minuto antes de tentar novamente

# Health Check API
app = Flask(__name__)
monitor = None

@app.route('/health')
def health_check():
    if monitor:
        return jsonify({
            "status": "healthy",
            "stats": monitor.stats,
            "timestamp": datetime.now().isoformat()
        })
    return jsonify({"status": "starting"}), 503

@app.route('/stats')
def get_stats():
    if monitor:
        return jsonify(monitor.stats)
    return jsonify({"error": "Monitor not initialized"}), 503

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == "__main__":
    # Verificar configuração
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram não configurado - notificações desabilitadas")
    
    # Criar diretório de logs
    os.makedirs('logs', exist_ok=True)
    
    # Iniciar API de health check em thread separada
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Iniciar monitor
    monitor = PriceMonitor()
    monitor.start()
