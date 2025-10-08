#!/bin/bash

# Script de inicialização do Flash Arbitrage Bot
set -e

echo "🚀 Iniciando Flash Arbitrage Bot..."

# Verificar se o arquivo .env existe
if [ ! -f .env ]; then
    echo "❌ Arquivo .env não encontrado!"
    echo "📝 Copie .env.example para .env e configure as variáveis:"
    echo "   cp .env.example .env"
    exit 1
fi

# Carregar variáveis de ambiente
source .env

# Verificar variáveis obrigatórias
required_vars=("TELEGRAM_BOT_TOKEN" "TELEGRAM_CHAT_ID" "ALCHEMY_API_KEY" "PRIVATE_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Variável $var não configurada no .env"
        exit 1
    fi
done

# Criar diretórios necessários
mkdir -p logs data

echo "✅ Configuração validada!"

# Escolher modo de execução
case "${1:-docker}" in
    "docker")
        echo "🐳 Iniciando com Docker..."
        docker-compose up -d
        echo "📊 Para ver logs: docker-compose logs -f"
        echo "🛑 Para parar: docker-compose down"
        ;;
    "local")
        echo "💻 Iniciando localmente..."
        python3 opportunity_monitor.py
        ;;
    "build")
        echo "🔨 Construindo imagem Docker..."
        docker-compose build
        ;;
    "monitoring")
        echo "📈 Iniciando com monitoramento..."
        docker-compose --profile monitoring up -d
        echo "📊 Grafana: http://localhost:3000 (admin/admin)"
        echo "📈 Prometheus: http://localhost:9090"
        ;;
    *)
        echo "Uso: $0 [docker|local|build|monitoring]"
        echo "  docker     - Executar com Docker (padrão)"
        echo "  local      - Executar localmente"
        echo "  build      - Construir imagem Docker"
        echo "  monitoring - Executar com monitoramento"
        exit 1
        ;;
esac
