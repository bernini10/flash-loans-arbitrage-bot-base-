#!/bin/bash

# Script de Deploy Automatizado - Flash Arbitrage Contract
# Versão: 1.0
# Autor: Manus AI

set -e  # Parar em caso de erro

echo "🚀 Iniciando deploy do FlashArbitrage Contract..."

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para log colorido
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar se estamos no diretório correto
if [ ! -f "contracts/FlashArbitrageComplete.sol" ]; then
    log_error "Arquivo do contrato não encontrado!"
    log_info "Certifique-se de estar no diretório correto: /root/flash-loans-arbitrage-bot"
    exit 1
fi

# Verificar se as variáveis de ambiente estão definidas
if [ -z "$PRIVATE_KEY" ]; then
    log_error "PRIVATE_KEY não definida no ambiente!"
    log_info "Execute: export PRIVATE_KEY=sua_chave_privada"
    exit 1
fi

if [ -z "$ALCHEMY_API_KEY" ]; then
    log_error "ALCHEMY_API_KEY não definida no ambiente!"
    log_info "Execute: export ALCHEMY_API_KEY=sua_api_key"
    exit 1
fi

# Carregar variáveis do .env se existir
if [ -f ".env" ]; then
    log_info "Carregando variáveis do arquivo .env..."
    source .env
fi

# Configurações
RPC_URL="https://base-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}"
AAVE_POOL_ADDRESS_PROVIDER="0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D"
CONTRACT_FILE="contracts/FlashArbitrageComplete.sol:FlashArbitrageComplete"

log_info "Configurações do deploy:"
echo "  - RPC URL: $RPC_URL"
echo "  - Aave Pool Address Provider: $AAVE_POOL_ADDRESS_PROVIDER"
echo "  - Contrato: $CONTRACT_FILE"

# Verificar se o Foundry está instalado
if ! command -v forge &> /dev/null; then
    log_warning "Foundry não encontrado. Instalando..."
    curl -L https://foundry.paradigm.xyz | bash
    source ~/.bashrc
    foundryup
fi

# Verificar versão do Foundry
log_info "Versão do Foundry: $(forge --version)"

# Compilar o contrato
log_info "Compilando contrato..."
if forge build --contracts contracts/FlashArbitrageComplete.sol; then
    log_success "Contrato compilado com sucesso!"
else
    log_error "Falha na compilação do contrato!"
    exit 1
fi

# Estimar gas para o deploy
log_info "Estimando gas para deploy..."
GAS_ESTIMATE=$(forge create --rpc-url "$RPC_URL" \
    --private-key "$PRIVATE_KEY" \
    --constructor-args "$AAVE_POOL_ADDRESS_PROVIDER" \
    "$CONTRACT_FILE" \
    --estimate-gas-only 2>/dev/null || echo "2000000")

log_info "Gas estimado: $GAS_ESTIMATE"

# Verificar saldo da conta
log_info "Verificando saldo da conta..."
ACCOUNT_ADDRESS=$(cast wallet address --private-key "$PRIVATE_KEY")
BALANCE=$(cast balance "$ACCOUNT_ADDRESS" --rpc-url "$RPC_URL")
BALANCE_ETH=$(cast --to-unit "$BALANCE" ether)

log_info "Endereço da conta: $ACCOUNT_ADDRESS"
log_info "Saldo: $BALANCE_ETH ETH"

# Verificar se há saldo suficiente (estimativa básica)
MIN_BALANCE_WEI="50000000000000000"  # 0.05 ETH
if [ "$BALANCE" -lt "$MIN_BALANCE_WEI" ]; then
    log_warning "Saldo pode ser insuficiente para o deploy!"
    log_info "Recomendado: pelo menos 0.05 ETH"
fi

# Fazer o deploy
log_info "Iniciando deploy do contrato..."
echo "⏳ Aguarde, isso pode levar alguns minutos..."

DEPLOY_OUTPUT=$(forge create --rpc-url "$RPC_URL" \
    --private-key "$PRIVATE_KEY" \
    --constructor-args "$AAVE_POOL_ADDRESS_PROVIDER" \
    "$CONTRACT_FILE" \
    --gas-limit "$GAS_ESTIMATE" 2>&1)

if echo "$DEPLOY_OUTPUT" | grep -q "Deployed to:"; then
    CONTRACT_ADDRESS=$(echo "$DEPLOY_OUTPUT" | grep "Deployed to:" | awk '{print $3}')
    TRANSACTION_HASH=$(echo "$DEPLOY_OUTPUT" | grep "Transaction hash:" | awk '{print $3}')
    
    log_success "🎉 Deploy realizado com sucesso!"
    echo ""
    echo "📋 INFORMAÇÕES DO DEPLOY:"
    echo "  📍 Endereço do Contrato: $CONTRACT_ADDRESS"
    echo "  🔗 Transaction Hash: $TRANSACTION_HASH"
    echo "  🌐 Network: Base Mainnet"
    echo "  👤 Deployer: $ACCOUNT_ADDRESS"
    echo ""
    
    # Atualizar arquivo .env
    if [ -f ".env" ]; then
        # Remover linha existente se houver
        sed -i '/^CONTRACT_ADDRESS=/d' .env
        # Adicionar nova linha
        echo "CONTRACT_ADDRESS=$CONTRACT_ADDRESS" >> .env
        log_success "Arquivo .env atualizado com o endereço do contrato!"
    else
        # Criar arquivo .env
        echo "CONTRACT_ADDRESS=$CONTRACT_ADDRESS" > .env
        log_success "Arquivo .env criado com o endereço do contrato!"
    fi
    
    # Verificar se o contrato foi deployado corretamente
    log_info "Verificando deploy..."
    OWNER=$(cast call "$CONTRACT_ADDRESS" "owner()" --rpc-url "$RPC_URL" 2>/dev/null || echo "")
    
    if [ -n "$OWNER" ]; then
        OWNER_ADDRESS=$(cast --to-checksum-address "0x$(echo $OWNER | sed 's/0x000000000000000000000000//')")
        log_success "✅ Contrato verificado! Owner: $OWNER_ADDRESS"
        
        if [ "$OWNER_ADDRESS" = "$ACCOUNT_ADDRESS" ]; then
            log_success "✅ Você é o owner do contrato!"
        else
            log_warning "⚠️ Owner do contrato é diferente da conta de deploy!"
        fi
    else
        log_warning "⚠️ Não foi possível verificar o contrato"
    fi
    
    # Salvar informações em arquivo
    DEPLOY_INFO_FILE="deploy_info_$(date +%Y%m%d_%H%M%S).json"
    cat > "$DEPLOY_INFO_FILE" << EOF
{
    "contract_address": "$CONTRACT_ADDRESS",
    "transaction_hash": "$TRANSACTION_HASH",
    "deployer_address": "$ACCOUNT_ADDRESS",
    "network": "base-mainnet",
    "aave_pool_address_provider": "$AAVE_POOL_ADDRESS_PROVIDER",
    "deploy_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "gas_used": "$GAS_ESTIMATE"
}
EOF
    
    log_success "Informações salvas em: $DEPLOY_INFO_FILE"
    
    echo ""
    echo "🎯 PRÓXIMOS PASSOS:"
    echo "1. ✅ Contrato deployado com sucesso"
    echo "2. 🔄 Execute: docker compose up -d --build"
    echo "3. 📊 Monitore os logs: docker compose logs -f"
    echo "4. 🌐 Acesse health check: http://localhost:8081/health"
    echo ""
    
else
    log_error "❌ Falha no deploy do contrato!"
    echo ""
    echo "📋 OUTPUT DO ERRO:"
    echo "$DEPLOY_OUTPUT"
    echo ""
    echo "🔧 POSSÍVEIS SOLUÇÕES:"
    echo "1. Verificar se há saldo suficiente na conta"
    echo "2. Verificar se a PRIVATE_KEY está correta"
    echo "3. Verificar se a ALCHEMY_API_KEY está correta"
    echo "4. Tentar novamente em alguns minutos"
    exit 1
fi

log_success "🏁 Script de deploy concluído!"
