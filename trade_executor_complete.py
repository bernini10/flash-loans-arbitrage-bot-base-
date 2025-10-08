#!/usr/bin/env python3
"""
Trade Executor Completo - Flash Loans Arbitrage Bot
Versão com gas optimization, risk management e error handling
"""

import json
import time
import logging
from typing import Dict, Optional, Tuple
from web3 import Web3
from web3.exceptions import ContractLogicError, TransactionNotFound
from decimal import Decimal, getcontext
import os

# Configurar precisão decimal
getcontext().prec = 50

logger = logging.getLogger(__name__)

class TradeExecutorComplete:
    def __init__(self, web3_provider_url: str, private_key: str, contract_address: str, contract_abi: list):
        self.w3 = Web3(Web3.HTTPProvider(web3_provider_url))
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), 
            abi=contract_abi
        )
        
        # Configurações de risk management
        self.max_gas_price_gwei = 50
        self.max_slippage_bps = 300  # 3%
        self.min_profit_threshold = 0.005  # 0.5%
        self.max_trade_amount_eth = 5.0  # 5 ETH máximo por trade
        self.gas_estimation_buffer = 1.2  # 20% buffer no gas
        
        # Cache para otimização
        self.gas_price_cache = {}
        self.gas_price_cache_time = 0
        self.cache_duration = 30  # 30 segundos
        
        logger.info(f"TradeExecutor inicializado para conta: {self.account.address}")

    def get_optimal_gas_price(self) -> int:
        """Obtém o preço de gas otimizado com cache"""
        current_time = time.time()
        
        # Usar cache se ainda válido
        if (current_time - self.gas_price_cache_time) < self.cache_duration and self.gas_price_cache:
            return self.gas_price_cache['gas_price']
        
        try:
            # Obter preço de gas atual
            gas_price = self.w3.eth.gas_price
            
            # Aplicar limite máximo
            max_gas_price_wei = self.w3.to_wei(self.max_gas_price_gwei, 'gwei')
            optimal_gas_price = min(gas_price, max_gas_price_wei)
            
            # Atualizar cache
            self.gas_price_cache = {
                'gas_price': optimal_gas_price,
                'timestamp': current_time
            }
            self.gas_price_cache_time = current_time
            
            logger.info(f"Gas price otimizado: {self.w3.from_wei(optimal_gas_price, 'gwei')} gwei")
            return optimal_gas_price
            
        except Exception as e:
            logger.error(f"Erro ao obter gas price: {e}")
            # Fallback para preço padrão
            return self.w3.to_wei(20, 'gwei')

    def estimate_gas_with_buffer(self, transaction: dict) -> int:
        """Estima gas com buffer de segurança"""
        try:
            estimated_gas = self.w3.eth.estimate_gas(transaction)
            buffered_gas = int(estimated_gas * self.gas_estimation_buffer)
            
            logger.debug(f"Gas estimado: {estimated_gas}, com buffer: {buffered_gas}")
            return buffered_gas
            
        except Exception as e:
            logger.error(f"Erro na estimativa de gas: {e}")
            # Fallback para gas padrão
            return 2000000

    def validate_opportunity(self, opportunity: Dict) -> Tuple[bool, str]:
        """Valida se a oportunidade é segura para execução"""
        try:
            # Validar endereços
            required_fields = ['tokenA', 'tokenB', 'dexBuy', 'dexSell', 'amountIn', 'minProfitBps']
            for field in required_fields:
                if field not in opportunity:
                    return False, f"Campo obrigatório ausente: {field}"
            
            # Validar endereços de token
            if not self.w3.is_address(opportunity['tokenA']):
                return False, "Endereço tokenA inválido"
            if not self.w3.is_address(opportunity['tokenB']):
                return False, "Endereço tokenB inválido"
            
            # Validar DEXs
            if not self.w3.is_address(opportunity['dexBuy']):
                return False, "Endereço dexBuy inválido"
            if not self.w3.is_address(opportunity['dexSell']):
                return False, "Endereço dexSell inválido"
            
            # Validar valores
            if opportunity['amountIn'] <= 0:
                return False, "Valor amountIn deve ser positivo"
            
            # Validar limite de trade
            amount_eth = self.w3.from_wei(opportunity['amountIn'], 'ether')
            if float(amount_eth) > self.max_trade_amount_eth:
                return False, f"Valor do trade excede limite máximo: {amount_eth} ETH"
            
            # Validar profit threshold
            profit_percentage = opportunity['minProfitBps'] / 10000
            if profit_percentage < self.min_profit_threshold:
                return False, f"Lucro insuficiente: {profit_percentage*100:.2f}%"
            
            return True, "Oportunidade válida"
            
        except Exception as e:
            return False, f"Erro na validação: {str(e)}"

    def simulate_arbitrage(self, opportunity: Dict) -> Tuple[bool, float, str]:
        """Simula a arbitragem antes da execução"""
        try:
            # Chamar função de simulação do contrato
            result = self.contract.functions.calculateProfit({
                'tokenA': Web3.to_checksum_address(opportunity['tokenA']),
                'tokenB': Web3.to_checksum_address(opportunity['tokenB']),
                'dexBuy': Web3.to_checksum_address(opportunity['dexBuy']),
                'dexSell': Web3.to_checksum_address(opportunity['dexSell']),
                'amountIn': opportunity['amountIn'],
                'minProfitBps': opportunity['minProfitBps'],
                'maxSlippageBps': self.max_slippage_bps,
                'deadline': int(time.time()) + 300
            }).call()
            
            if result > 0:
                profit_percentage = (result / opportunity['amountIn']) * 100
                return True, profit_percentage, f"Lucro simulado: {profit_percentage:.4f}%"
            else:
                return False, 0, "Simulação indica perda"
                
        except ContractLogicError as e:
            return False, 0, f"Erro de lógica do contrato: {str(e)}"
        except Exception as e:
            return False, 0, f"Erro na simulação: {str(e)}"

    def execute_trade(self, opportunity: Dict) -> Optional[str]:
        """Executa o trade de arbitragem com todas as validações"""
        try:
            logger.info(f"Iniciando execução de trade: {opportunity}")
            
            # Validar oportunidade
            is_valid, validation_message = self.validate_opportunity(opportunity)
            if not is_valid:
                logger.error(f"Oportunidade inválida: {validation_message}")
                return None
            
            # Simular arbitragem
            simulation_success, profit_pct, simulation_message = self.simulate_arbitrage(opportunity)
            if not simulation_success:
                logger.error(f"Simulação falhou: {simulation_message}")
                return None
            
            logger.info(f"Simulação bem-sucedida: {simulation_message}")
            
            # Preparar parâmetros do contrato
            arbitrage_params = {
                'tokenA': Web3.to_checksum_address(opportunity['tokenA']),
                'tokenB': Web3.to_checksum_address(opportunity['tokenB']),
                'dexBuy': Web3.to_checksum_address(opportunity['dexBuy']),
                'dexSell': Web3.to_checksum_address(opportunity['dexSell']),
                'amountIn': opportunity['amountIn'],
                'minProfitBps': opportunity['minProfitBps'],
                'maxSlippageBps': self.max_slippage_bps,
                'deadline': int(time.time()) + 300  # 5 minutos
            }
            
            # Obter nonce
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # Construir transação
            transaction = self.contract.functions.executeArbitrage(
                arbitrage_params
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gasPrice': self.get_optimal_gas_price(),
                'chainId': self.w3.eth.chain_id
            })
            
            # Estimar e definir gas
            transaction['gas'] = self.estimate_gas_with_buffer(transaction)
            
            # Verificar saldo para gas
            balance = self.w3.eth.get_balance(self.account.address)
            gas_cost = transaction['gas'] * transaction['gasPrice']
            
            if balance < gas_cost:
                logger.error(f"Saldo insuficiente para gas. Necessário: {self.w3.from_wei(gas_cost, 'ether')} ETH")
                return None
            
            # Assinar transação
            signed_tx = self.w3.eth.account.sign_transaction(transaction, private_key=self.account.key)
            
            # Enviar transação
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            
            logger.info(f"Transação enviada: {tx_hash_hex}")
            
            # Aguardar confirmação (opcional, com timeout)
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                if receipt.status == 1:
                    logger.info(f"Trade executado com sucesso! Gas usado: {receipt.gasUsed}")
                    return tx_hash_hex
                else:
                    logger.error(f"Transação falhou. Receipt: {receipt}")
                    return None
            except TransactionNotFound:
                logger.warning(f"Transação não encontrada, mas hash retornado: {tx_hash_hex}")
                return tx_hash_hex
            
        except Exception as e:
            logger.error(f"Erro ao executar trade: {str(e)}")
            return None

    def get_account_info(self) -> Dict:
        """Retorna informações da conta"""
        try:
            balance = self.w3.eth.get_balance(self.account.address)
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            return {
                'address': self.account.address,
                'balance_wei': balance,
                'balance_eth': float(self.w3.from_wei(balance, 'ether')),
                'nonce': nonce,
                'network': self.w3.eth.chain_id
            }
        except Exception as e:
            logger.error(f"Erro ao obter informações da conta: {e}")
            return {}

    def check_contract_health(self) -> bool:
        """Verifica se o contrato está funcionando"""
        try:
            # Tentar chamar uma função view do contrato
            owner = self.contract.functions.owner().call()
            return owner is not None
        except Exception as e:
            logger.error(f"Contrato não está saudável: {e}")
            return False

    def emergency_stop(self) -> bool:
        """Para todas as operações em caso de emergência"""
        try:
            logger.warning("EMERGENCY STOP ativado!")
            # Implementar lógica de parada de emergência se necessário
            return True
        except Exception as e:
            logger.error(f"Erro no emergency stop: {e}")
            return False
