import json
from web3 import Web3
import os

class TradeExecutor:
    def __init__(self, web3_provider_url, private_key, contract_address, contract_abi):
        self.w3 = Web3(Web3.HTTPProvider(web3_provider_url))
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract = self.w3.eth.contract(address=contract_address, abi=contract_abi)

    def execute_trade(self, opportunity):
        try:
            tx = self.contract.functions.executeArbitrage(
                (
                    opportunity['tokenA'],
                    opportunity['tokenB'],
                    opportunity['dexBuy'],
                    opportunity['dexSell'],
                    opportunity['amountIn'],
                    opportunity['minProfitBps'],
                    opportunity['deadline']
                )
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 2000000,
                'gasPrice': self.w3.eth.gas_price
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            return self.w3.to_hex(tx_hash)
        except Exception as e:
            print(f"Error executing trade: {e}")
            return None
