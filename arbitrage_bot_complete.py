#!/usr/bin/env python3
"""
Flash Loans Arbitrage Bot - Sistema Completo
Versão final com execução automática, risk management e monitoramento avançado
"""

import json
import time
import logging
import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from web3 import Web3
import requests
from flask import Flask, jsonify, request
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Importar o executor completo
from trade_executor_complete import TradeExecutorComplete

# Configuração de logging avançada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/arbitrage_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class OpportunityStats:
    total_found: int = 0
    total_executed: int = 0
    total_profitable: int = 0
    total_failed: int = 0
    total_profit_wei: int = 0
    avg_profit_percentage: float = 0.0
    last_execution: Optional[datetime] = None

class Config:
    # Conexão Web3
    ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY", "akWmmJe92KBl0WdKklCYXx1UW5msrmv0")
    WEB3_PROVIDER_URL = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    
    # Chaves e Contratos
    PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
    CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS")
    
    # Notificações
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    
    # Parâmetros de Trading
    MIN_PROFIT_THRESHOLD = float(os.environ.get("MIN_PROFIT_THRESHOLD", "0.005"))  # 0.5%
    MAX_SLIPPAGE_BPS = int(os.environ.get("MAX_SLIPPAGE_BPS", "300"))  # 3%
    MAX_GAS_PRICE_GWEI = int(os.environ.get("MAX_GAS_PRICE_GWEI", "50"))
    
    # Valores de Flash Loan
    FLASH_LOAN_AMOUNT_WETH = int(float(os.environ.get("FLASH_LOAN_AMOUNT_WETH", "1.0")) * (10**18))
    FLASH_LOAN_AMOUNT_USDC = int(float(os.environ.get("FLASH_LOAN_AMOUNT_USDC", "1000.0")) * (10**6))
    
    # Timings
    API_CALL_DELAY = int(os.environ.get("API_CALL_DELAY", "2"))
    CYCLE_DELAY = int(os.environ.get("CYCLE_DELAY", "180"))  # 3 minutos
    HEALTH_CHECK_INTERVAL = int(os.environ.get("HEALTH_CHECK_INTERVAL", "300"))  # 5 minutos
    
    # Risk Management
    MAX_DAILY_TRADES = int(os.environ.get("MAX_DAILY_TRADES", "50"))
    MAX_CONSECUTIVE_FAILURES = int(os.environ.get("MAX_CONSECUTIVE_FAILURES", "5"))
    EMERGENCY_STOP_LOSS_PCT = float(os.environ.get("EMERGENCY_STOP_LOSS_PCT", "5.0"))  # 5%

# Carregar ABI do contrato
try:
    with open("contracts/FlashArbitrage.json", "r") as f:
        FLASH_ARBITRAGE_ABI = json.load(f)["abi"]
except FileNotFoundError:
    logger.error("Arquivo ABI não encontrado. Usando ABI básico.")
    FLASH_ARBITRAGE_ABI = []

# Configurações de DEXs e Tokens
DEXS = {
    "Uniswap V3": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
    "SushiSwap V3": "0x57713f7716e0b0f65ec116912f834e49805480d2", 
    "Aerodrome": "0xcdac0d6c6c59727a65f871236188350531885c43",
}

TOKENS = {
    "WETH": "0x4200000000000000000000000000000000000006",
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

# ABIs necessários
ERC20_ABI = [{"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]

UNISWAP_V3_POOL_ABI = [
    {"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"}],"stateMutability":"view","type":"function"},
    {"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}
]

class RateLimiter:
    def __init__(self, delay: float):
        self.delay = delay
        self.last_call = 0
        self.lock = threading.Lock()
    
    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_call = time.time()

class TelegramNotifier:
    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.rate_limiter = RateLimiter(1.0)
        self.session = requests.Session()
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram não configurado")
            return False
        
        self.rate_limiter.wait()
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message[:4096],  # Limite do Telegram
            "parse_mode": parse_mode
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False

class ArbitrageBotComplete:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(Config.WEB3_PROVIDER_URL))
        self.rate_limiter = RateLimiter(Config.API_CALL_DELAY)
        self.telegram = TelegramNotifier()
        self.executor = None
        
        # Estatísticas
        self.stats = OpportunityStats()
        self.daily_trades = 0
        self.consecutive_failures = 0
        self.last_reset_date = datetime.now().date()
        self.emergency_stop = False
        
        # Thread pool para execução paralela
        self.executor_pool = ThreadPoolExecutor(max_workers=3)
        
        # Inicializar executor de trades
        if Config.PRIVATE_KEY and Config.CONTRACT_ADDRESS:
            try:
                self.executor = TradeExecutorComplete(
                    web3_provider_url=Config.WEB3_PROVIDER_URL,
                    private_key=Config.PRIVATE_KEY,
                    contract_address=Config.CONTRACT_ADDRESS,
                    contract_abi=FLASH_ARBITRAGE_ABI
                )
                logger.info("✅ Executor de trades inicializado - MODO AUTOMÁTICO")
                
                # Enviar informações da conta
                account_info = self.executor.get_account_info()
                self.telegram.send_message(
                    f"🤖 *Bot Iniciado - MODO AUTOMÁTICO*\n\n"
                    f"💰 *Saldo:* {account_info.get('balance_eth', 0):.4f} ETH\n"
                    f"🔗 *Rede:* Base (Chain ID: {account_info.get('network', 'N/A')})\n"
                    f"📊 *Threshold:* {Config.MIN_PROFIT_THRESHOLD*100:.2f}%\n"
                    f"⛽ *Max Gas:* {Config.MAX_GAS_PRICE_GWEI} gwei"
                )
                
            except Exception as e:
                logger.error(f"Erro ao inicializar executor: {e}")
                self.telegram.send_message(f"❌ *Erro ao inicializar executor:* {str(e)}")
        else:
            logger.warning("🔍 Executor não inicializado - MODO SOMENTE MONITOR")
            self.telegram.send_message("🔍 *Bot iniciado em MODO SOMENTE MONITOR*")

    def reset_daily_stats(self):
        """Reset estatísticas diárias"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_trades = 0
            self.last_reset_date = current_date
            logger.info("Estatísticas diárias resetadas")

    def check_emergency_conditions(self) -> bool:
        """Verifica condições de parada de emergência"""
        if self.consecutive_failures >= Config.MAX_CONSECUTIVE_FAILURES:
            logger.error(f"EMERGENCY STOP: {self.consecutive_failures} falhas consecutivas")
            self.emergency_stop = True
            self.telegram.send_message(
                f"🚨 *EMERGENCY STOP ATIVADO*\n\n"
                f"❌ *Falhas consecutivas:* {self.consecutive_failures}\n"
                f"⏸️ *Bot pausado automaticamente*"
            )
            return True
        
        if self.daily_trades >= Config.MAX_DAILY_TRADES:
            logger.warning(f"Limite diário de trades atingido: {self.daily_trades}")
            return True
            
        return False

    def get_token_decimals(self, token_address: str) -> Optional[int]:
        """Obtém decimais do token com cache"""
        try:
            self.rate_limiter.wait()
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address), 
                abi=ERC20_ABI
            )
            return token_contract.functions.decimals().call()
        except Exception as e:
            logger.error(f"Erro ao obter decimais do token {token_address}: {e}")
            return None

    def get_uniswap_v3_price(self, pool_address: str, token_in: str, token_out: str) -> Optional[float]:
        """Obtém preço do Uniswap V3"""
        try:
            self.rate_limiter.wait()
            pool_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=UNISWAP_V3_POOL_ABI
            )
            
            slot0 = pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            
            if sqrt_price_x96 == 0:
                return None
            
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
            
            return price if price > 0 else None
            
        except Exception as e:
            logger.debug(f"Erro ao obter preço Uniswap V3: {e}")
            return None

    def calculate_profit_after_gas(self, profit_wei: int, gas_cost_wei: int) -> float:
        """Calcula lucro líquido após custos de gas"""
        net_profit_wei = profit_wei - gas_cost_wei
        if net_profit_wei <= 0:
            return 0.0
        return net_profit_wei / profit_wei

    def check_arbitrage_opportunities(self) -> List[Dict]:
        """Verifica oportunidades de arbitragem"""
        opportunities = []
        
        for dex1_name, dex1_address in DEXS.items():
            for dex2_name, dex2_address in DEXS.items():
                if dex1_name == dex2_name:
                    continue
                
                for token1_symbol, token1_address in TOKENS.items():
                    for token2_symbol, token2_address in TOKENS.items():
                        if token1_symbol == token2_symbol:
                            continue
                        
                        try:
                            price1 = self.get_uniswap_v3_price(dex1_address, token1_address, token2_address)
                            price2 = self.get_uniswap_v3_price(dex2_address, token1_address, token2_address)
                            
                            if price1 and price2 and price1 > 0 and price2 > 0:
                                profit = (price2 / price1) - 1
                                
                                if profit > Config.MIN_PROFIT_THRESHOLD:
                                    amount_in = (Config.FLASH_LOAN_AMOUNT_WETH 
                                               if token1_symbol == 'WETH' 
                                               else Config.FLASH_LOAN_AMOUNT_USDC)
                                    
                                    opportunity = {
                                        'tokenA': Web3.to_checksum_address(token1_address),
                                        'tokenB': Web3.to_checksum_address(token2_address),
                                        'dexBuy': Web3.to_checksum_address(dex1_address),
                                        'dexSell': Web3.to_checksum_address(dex2_address),
                                        'amountIn': amount_in,
                                        'minProfitBps': int(profit * 10000),
                                        'deadline': int(time.time()) + 300,
                                        'profit_percentage': profit * 100,
                                        'token_pair': f"{token1_symbol}/{token2_symbol}",
                                        'dex_pair': f"{dex1_name} → {dex2_name}",
                                        'price_buy': price1,
                                        'price_sell': price2
                                    }
                                    
                                    opportunities.append(opportunity)
                                    
                        except Exception as e:
                            logger.debug(f"Erro ao processar {token1_symbol}/{token2_symbol}: {e}")
        
        return opportunities

    def execute_opportunity(self, opportunity: Dict) -> bool:
        """Executa uma oportunidade de arbitragem"""
        try:
            if not self.executor:
                return False
            
            logger.info(f"🚀 Executando oportunidade: {opportunity['token_pair']} - {opportunity['profit_percentage']:.3f}%")
            
            tx_hash = self.executor.execute_trade(opportunity)
            
            if tx_hash:
                self.stats.total_executed += 1
                self.daily_trades += 1
                self.consecutive_failures = 0
                self.stats.last_execution = datetime.now()
                
                # Notificar sucesso
                message = (
                    f"✅ *Trade Executado com Sucesso!*\n\n"
                    f"💰 *Lucro Estimado:* {opportunity['profit_percentage']:.3f}%\n"
                    f"🔄 *Par:* {opportunity['token_pair']}\n"
                    f"📈 *Rota:* {opportunity['dex_pair']}\n"
                    f"🔗 *TX Hash:* `{tx_hash}`\n"
                    f"📊 *Trades Hoje:* {self.daily_trades}/{Config.MAX_DAILY_TRADES}"
                )
                self.telegram.send_message(message)
                
                return True
            else:
                self.consecutive_failures += 1
                self.stats.total_failed += 1
                
                # Notificar falha
                self.telegram.send_message(
                    f"❌ *Falha na Execução*\n\n"
                    f"🔄 *Par:* {opportunity['token_pair']}\n"
                    f"💰 *Lucro Esperado:* {opportunity['profit_percentage']:.3f}%\n"
                    f"⚠️ *Falhas Consecutivas:* {self.consecutive_failures}"
                )
                
                return False
                
        except Exception as e:
            logger.error(f"Erro ao executar oportunidade: {e}")
            self.consecutive_failures += 1
            self.stats.total_failed += 1
            return False

    def run_monitoring_cycle(self):
        """Executa um ciclo de monitoramento"""
        try:
            self.reset_daily_stats()
            
            if self.check_emergency_conditions():
                return
            
            logger.info("🔍 Iniciando ciclo de monitoramento...")
            opportunities = self.check_arbitrage_opportunities()
            
            self.stats.total_found += len(opportunities)
            
            if opportunities:
                # Ordenar por lucro (maior primeiro)
                opportunities.sort(key=lambda x: x['profit_percentage'], reverse=True)
                
                logger.info(f"📊 Encontradas {len(opportunities)} oportunidades")
                
                # Executar apenas a melhor oportunidade por ciclo
                best_opportunity = opportunities[0]
                
                if self.executor:
                    success = self.execute_opportunity(best_opportunity)
                    if success:
                        self.stats.total_profitable += 1
                else:
                    # Modo somente monitor
                    message = (
                        f"🔍 *Oportunidade Detectada (MONITOR)*\n\n"
                        f"💰 *Lucro Estimado:* {best_opportunity['profit_percentage']:.3f}%\n"
                        f"🔄 *Par:* {best_opportunity['token_pair']}\n"
                        f"📈 *Rota:* {best_opportunity['dex_pair']}\n"
                        f"💵 *Preço Compra:* {best_opportunity['price_buy']:.6f}\n"
                        f"💵 *Preço Venda:* {best_opportunity['price_sell']:.6f}"
                    )
                    self.telegram.send_message(message)
            
            logger.info(f"✅ Ciclo concluído. Stats: {self.stats.total_found} encontradas, {self.stats.total_executed} executadas")
            
        except Exception as e:
            logger.error(f"Erro no ciclo de monitoramento: {e}")
            self.telegram.send_message(f"❌ *Erro no monitoramento:* {str(e)}")

    def start_monitoring(self):
        """Inicia o monitoramento contínuo"""
        logger.info("🚀 Iniciando monitoramento de arbitragem...")
        
        while not self.emergency_stop:
            try:
                self.run_monitoring_cycle()
                
                logger.info(f"⏳ Aguardando {Config.CYCLE_DELAY} segundos para próximo ciclo...")
                time.sleep(Config.CYCLE_DELAY)
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot interrompido pelo usuário")
                self.telegram.send_message("🛑 *Bot parado pelo usuário*")
                break
            except Exception as e:
                logger.error(f"Erro crítico: {e}")
                self.telegram.send_message(f"🚨 *Erro crítico:* {str(e)}")
                time.sleep(60)

# API Flask para monitoramento
app = Flask(__name__)
bot_instance = None

@app.route('/health')
def health_check():
    if bot_instance:
        return jsonify({
            "status": "healthy",
            "stats": {
                "total_found": bot_instance.stats.total_found,
                "total_executed": bot_instance.stats.total_executed,
                "total_profitable": bot_instance.stats.total_profitable,
                "total_failed": bot_instance.stats.total_failed,
                "daily_trades": bot_instance.daily_trades,
                "consecutive_failures": bot_instance.consecutive_failures,
                "emergency_stop": bot_instance.emergency_stop,
                "last_execution": bot_instance.stats.last_execution.isoformat() if bot_instance.stats.last_execution else None
            },
            "timestamp": datetime.now().isoformat()
        })
    return jsonify({"status": "starting"}), 503

@app.route('/stats')
def get_stats():
    if bot_instance:
        account_info = {}
        if bot_instance.executor:
            account_info = bot_instance.executor.get_account_info()
        
        return jsonify({
            "trading_stats": {
                "total_found": bot_instance.stats.total_found,
                "total_executed": bot_instance.stats.total_executed,
                "success_rate": (bot_instance.stats.total_profitable / max(bot_instance.stats.total_executed, 1)) * 100,
                "daily_trades": bot_instance.daily_trades,
                "max_daily_trades": Config.MAX_DAILY_TRADES
            },
            "account_info": account_info,
            "config": {
                "min_profit_threshold": Config.MIN_PROFIT_THRESHOLD,
                "max_gas_price_gwei": Config.MAX_GAS_PRICE_GWEI,
                "cycle_delay": Config.CYCLE_DELAY
            }
        })
    return jsonify({"error": "Bot not initialized"}), 503

@app.route('/emergency-stop', methods=['POST'])
def emergency_stop():
    if bot_instance:
        bot_instance.emergency_stop = True
        if bot_instance.executor:
            bot_instance.executor.emergency_stop()
        return jsonify({"status": "Emergency stop activated"})
    return jsonify({"error": "Bot not initialized"}), 503

def run_flask():
    app.run(host='0.0.0.0', port=8081, debug=False)

if __name__ == "__main__":
    # Verificar configuração
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram não configurado - notificações desabilitadas")
    
    if not Config.PRIVATE_KEY or not Config.CONTRACT_ADDRESS:
        logger.warning("⚠️ Chaves não configuradas - rodando em modo SOMENTE MONITOR")
    
    # Criar diretório de logs
    os.makedirs('logs', exist_ok=True)
    
    # Iniciar API Flask em thread separada
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Inicializar e iniciar bot
    bot_instance = ArbitrageBotComplete()
    bot_instance.start_monitoring()
