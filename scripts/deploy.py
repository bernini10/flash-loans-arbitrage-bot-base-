import os
from web3 import Web3
from dotenv import load_dotenv
import json

load_dotenv()

# --- Configuração ---
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
ALCHEMY_URL = os.environ.get("ALCHEMY_URL")

w3 = Web3(Web3.HTTPProvider(ALCHEMY_URL))

# --- Carregar Artefatos do Contrato ---
with open("../artifacts/contracts/FlashArbitrage.sol/FlashArbitrage.json") as f:
    contract_json = json.load(f)
    contract_abi = contract_json["abi"]
    contract_bytecode = contract_json["bytecode"]

# --- Implantação ---
def deploy():
    if not PRIVATE_KEY:
        print("Erro: A chave privada não foi definida. Por favor, defina a variável de ambiente PRIVATE_KEY.")
        return

    account = w3.eth.account.from_key(PRIVATE_KEY)
    w3.eth.default_account = account.address

    print(f"A implantar o contrato a partir da conta: {account.address}")

    FlashArbitrage = w3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)

    # Endereço do PoolAddressesProvider da Aave na Base (mesmo da Optimism)
    AAVE_POOL_ADDRESSES_PROVIDER = "0xa97684ead0e402dc232d5a977953df7ecbab3cdb"

    # Estimar o gás
    gas_estimate = FlashArbitrage.constructor(
        AAVE_POOL_ADDRESSES_PROVIDER
    ).estimate_gas()

    # Construir a transação
    tx = FlashArbitrage.constructor(
        AAVE_POOL_ADDRESSES_PROVIDER
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": gas_estimate,
        "gasPrice": w3.eth.gas_price,
    })

    # Assinar e enviar a transação
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    print(f"Transação de implantação enviada. Hash: {w3.to_hex(tx_hash)}")

    # Aguardar a confirmação da transação
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(f"Contrato implantado com sucesso no endereço: {tx_receipt.contractAddress}")
    return tx_receipt.contractAddress

if __name__ == "__main__":
    deploy()

