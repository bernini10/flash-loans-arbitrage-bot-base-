#!/bin/bash

# Setup e Execução Completa - Flash Arbitrage Bot
# ================================================
# Este script automatiza todo o processo de setup e execução

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Funções de log
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${PURPLE}[STEP]${NC} $1"; }

# Banner
echo -e "${CYAN}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🚀 FLASH LOANS ARBITRAGE BOT - SETUP COMPLETO        ║
║                                                              ║
║                    Versão: 1.0.0                            ║
║                    Autor: Manus AI                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Verificar se estamos no diretório correto
if [ ! -f "arbitrage_bot_complete.py" ]; then
    log_error "Arquivo principal não encontrado!"
    log_info "Execute este script no diretório: /root/flash-loans-arbitrage-bot"
    exit 1
fi

log_step "1/8 - Verificando dependências do sistema..."

# Verificar Docker
if ! command -v docker &> /dev/null; then
    log_warning "Docker não encontrado. Instalando..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $USER
    systemctl start docker
    systemctl enable docker
    log_success "Docker instalado!"
else
    log_success "Docker encontrado: $(docker --version)"
fi

# Verificar Docker Compose
if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
    log_warning "Docker Compose não encontrado. Instalando..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_success "Docker Compose instalado!"
else
    log_success "Docker Compose encontrado: $(docker compose version)"
fi

log_step "2/8 - Configurando ambiente..."

# Copiar arquivo de configuração
if [ ! -f ".env" ]; then
    if [ -f ".env.production" ]; then
        cp .env.production .env
        log_success "Arquivo .env criado a partir do template de produção"
    else
        log_error "Arquivo .env.production não encontrado!"
        exit 1
    fi
else
    log_info "Arquivo .env já existe"
fi

# Verificar se as chaves estão configuradas
source .env

if [ -z "$PRIVATE_KEY" ] || [ "$PRIVATE_KEY" = "sua_private_key_aqui" ]; then
    log_error "PRIVATE_KEY não configurada no arquivo .env!"
    log_info "Edite o arquivo .env e configure sua chave privada"
    exit 1
fi

if [ -z "$ALCHEMY_API_KEY" ] || [ "$ALCHEMY_API_KEY" = "sua_api_key_aqui" ]; then
    log_error "ALCHEMY_API_KEY não configurada no arquivo .env!"
    log_info "Edite o arquivo .env e configure sua API key da Alchemy"
    exit 1
fi

log_step "3/8 - Verificando saldo da conta..."

# Instalar cast se necessário
if ! command -v cast &> /dev/null; then
    log_info "Instalando Foundry para verificações..."
    curl -L https://foundry.paradigm.xyz | bash
    source ~/.bashrc
    foundryup
fi

# Verificar saldo
ACCOUNT_ADDRESS=$(cast wallet address --private-key "$PRIVATE_KEY" 2>/dev/null || echo "")
if [ -n "$ACCOUNT_ADDRESS" ]; then
    RPC_URL="https://base-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}"
    BALANCE=$(cast balance "$ACCOUNT_ADDRESS" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
    BALANCE_ETH=$(cast --to-unit "$BALANCE" ether 2>/dev/null || echo "0")
    
    log_info "Endereço da conta: $ACCOUNT_ADDRESS"
    log_info "Saldo: $BALANCE_ETH ETH"
    
    # Verificar saldo mínimo
    if (( $(echo "$BALANCE_ETH < 0.1" | bc -l) )); then
        log_warning "Saldo baixo! Recomendado: pelo menos 0.1 ETH"
        log_info "Você pode continuar, mas pode não conseguir executar trades"
    else
        log_success "Saldo suficiente para operação"
    fi
else
    log_warning "Não foi possível verificar o saldo da conta"
fi

log_step "4/8 - Verificando contrato..."

if [ -z "$CONTRACT_ADDRESS" ] || [ "$CONTRACT_ADDRESS" = "" ]; then
    log_warning "Contrato não deployado ainda"
    
    read -p "Deseja fazer o deploy do contrato agora? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Iniciando deploy do contrato..."
        
        if ./deploy_contract.sh; then
            log_success "Contrato deployado com sucesso!"
            # Recarregar .env para pegar o novo CONTRACT_ADDRESS
            source .env
        else
            log_error "Falha no deploy do contrato!"
            exit 1
        fi
    else
        log_warning "Continuando sem deploy. Bot rodará em modo MONITOR apenas."
    fi
else
    log_success "Contrato já configurado: $CONTRACT_ADDRESS"
fi

log_step "5/8 - Preparando arquivos Docker..."

# Usar arquivos completos
if [ -f "Dockerfile.complete" ]; then
    cp Dockerfile.complete Dockerfile
    log_success "Dockerfile atualizado"
fi

if [ -f "docker-compose.complete.yml" ]; then
    cp docker-compose.complete.yml docker-compose.yml
    log_success "docker-compose.yml atualizado"
fi

# Criar diretórios necessários
mkdir -p logs data backups monitoring/grafana/dashboards monitoring/grafana/datasources

log_step "6/8 - Construindo imagem Docker..."

if docker compose build; then
    log_success "Imagem Docker construída com sucesso!"
else
    log_error "Falha na construção da imagem Docker!"
    exit 1
fi

log_step "7/8 - Iniciando serviços..."

# Parar serviços existentes se houver
docker compose down 2>/dev/null || true

# Iniciar serviços
if docker compose up -d; then
    log_success "Serviços iniciados com sucesso!"
else
    log_error "Falha ao iniciar serviços!"
    exit 1
fi

log_step "8/8 - Verificando status..."

# Aguardar alguns segundos para os serviços iniciarem
sleep 10

# Verificar se o container está rodando
if docker compose ps | grep -q "Up"; then
    log_success "Container está rodando!"
else
    log_error "Container não está rodando!"
    log_info "Verificando logs..."
    docker compose logs --tail=20
    exit 1
fi

# Verificar health check
log_info "Aguardando health check..."
sleep 20

if curl -f http://localhost:8081/health &>/dev/null; then
    log_success "Health check passou!"
else
    log_warning "Health check falhou, mas o container está rodando"
fi

# Mostrar informações finais
echo ""
echo -e "${GREEN}🎉 SETUP COMPLETO! 🎉${NC}"
echo ""
echo -e "${CYAN}📊 INFORMAÇÕES DO SISTEMA:${NC}"
echo "  🔗 API Health Check: http://localhost:8081/health"
echo "  📈 Estatísticas: http://localhost:8081/stats"
echo "  🐳 Container: flash-arbitrage-bot-complete"
echo ""

if [ -n "$CONTRACT_ADDRESS" ]; then
    echo -e "${GREEN}✅ MODO: EXECUÇÃO AUTOMÁTICA${NC}"
    echo "  📍 Contrato: $CONTRACT_ADDRESS"
    echo "  💰 Threshold: ${MIN_PROFIT_THRESHOLD:-0.005}% (${MIN_PROFIT_THRESHOLD:-0.5}%)"
else
    echo -e "${YELLOW}🔍 MODO: SOMENTE MONITOR${NC}"
    echo "  ⚠️ Contrato não configurado - apenas detectará oportunidades"
fi

echo ""
echo -e "${CYAN}📋 COMANDOS ÚTEIS:${NC}"
echo "  📊 Ver logs: docker compose logs -f"
echo "  🔄 Reiniciar: docker compose restart"
echo "  🛑 Parar: docker compose down"
echo "  📈 Status: docker compose ps"
echo "  🏥 Health: curl http://localhost:8081/health"
echo ""

echo -e "${CYAN}🔔 NOTIFICAÇÕES:${NC}"
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    echo "  ✅ Telegram configurado"
    echo "  📱 Chat ID: $TELEGRAM_CHAT_ID"
else
    echo "  ⚠️ Telegram não configurado"
fi

echo ""
echo -e "${PURPLE}🚀 O bot está rodando! Monitore os logs para ver as oportunidades.${NC}"
echo ""

# Mostrar logs em tempo real
read -p "Deseja ver os logs em tempo real? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Mostrando logs em tempo real (Ctrl+C para sair):${NC}"
    echo ""
    docker compose logs -f
fi

log_success "🏁 Setup e execução concluídos com sucesso!"
