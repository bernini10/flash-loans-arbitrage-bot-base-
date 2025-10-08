# 🚀 Flash Loans Arbitrage Bot - Sistema Completo

## 📋 Visão Geral

Sistema completo de arbitragem automatizada usando Flash Loans na rede Base. O bot detecta oportunidades de arbitragem entre diferentes DEXs e executa trades automaticamente para capturar lucros.

### ✨ Características Principais

- 🤖 **Execução Automática**: Detecta e executa trades automaticamente
- 🛡️ **Risk Management**: Sistema avançado de gerenciamento de risco
- ⚡ **Gas Optimization**: Otimização inteligente de gas fees
- 📊 **Monitoramento Avançado**: APIs de health check e estatísticas
- 📱 **Notificações Telegram**: Alertas em tempo real
- 🐳 **Docker Ready**: Deploy fácil com Docker
- 🔒 **Segurança**: Validações e emergency stop

## 🏗️ Arquitetura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Monitor Bot   │───▶│  Trade Executor │───▶│ Smart Contract  │
│                 │    │                 │    │                 │
│ - Detecta opor. │    │ - Valida trades │    │ - Flash Loans   │
│ - Calcula lucro │    │ - Executa TX    │    │ - Arbitragem    │
│ - Risk mgmt     │    │ - Gas optim.    │    │ - Safety checks │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Telegram     │    │   Health API    │    │      DEXs       │
│  Notifications  │    │   (Port 8081)   │    │ - Uniswap V3    │
│                 │    │                 │    │ - SushiSwap V3  │
│ - Alertas       │    │ - /health       │    │ - Aerodrome     │
│ - Estatísticas  │    │ - /stats        │    │ - Outros...     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Pré-requisitos

- Ubuntu 20.04+ ou similar
- Docker e Docker Compose
- Conta com ETH na rede Base
- Chave API da Alchemy
- Bot do Telegram (opcional)

### Instalação Automática

```bash
# 1. Clonar ou fazer upload dos arquivos
cd /root/flash-loans-arbitrage-bot

# 2. Executar setup completo
./setup_and_run.sh
```

O script automaticamente:
- ✅ Instala dependências (Docker, Foundry)
- ✅ Configura ambiente
- ✅ Faz deploy do contrato
- ✅ Constrói imagem Docker
- ✅ Inicia o bot

### Instalação Manual

```bash
# 1. Configurar ambiente
cp .env.production .env
nano .env  # Editar com suas chaves

# 2. Deploy do contrato
./deploy_contract.sh

# 3. Construir e executar
docker compose up -d --build

# 4. Verificar status
docker compose logs -f
```

## ⚙️ Configuração

### Arquivo .env

```bash
# Chaves obrigatórias
PRIVATE_KEY=sua_chave_privada
ALCHEMY_API_KEY=sua_api_key
CONTRACT_ADDRESS=endereco_do_contrato

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id

# Parâmetros de trading
MIN_PROFIT_THRESHOLD=0.005    # 0.5% lucro mínimo
MAX_GAS_PRICE_GWEI=50        # 50 gwei máximo
FLASH_LOAN_AMOUNT_WETH=1.0   # 1 WETH por trade
```

### Risk Management

```bash
MAX_DAILY_TRADES=50              # Máximo 50 trades/dia
MAX_CONSECUTIVE_FAILURES=5       # Parar após 5 falhas
EMERGENCY_STOP_LOSS_PCT=5.0     # Emergency stop com 5% perda
```

## 📊 Monitoramento

### APIs Disponíveis

```bash
# Health check
curl http://localhost:8081/health

# Estatísticas detalhadas
curl http://localhost:8081/stats

# Emergency stop
curl -X POST http://localhost:8081/emergency-stop
```

### Logs

```bash
# Ver logs em tempo real
docker compose logs -f

# Ver logs específicos
docker compose logs flash-arbitrage-bot

# Logs salvos em arquivo
tail -f logs/arbitrage_bot.log
```

## 🔧 Comandos Úteis

### Docker

```bash
# Iniciar serviços
docker compose up -d

# Parar serviços
docker compose down

# Reiniciar
docker compose restart

# Rebuild
docker compose up -d --build

# Ver status
docker compose ps
```

### Manutenção

```bash
# Verificar saldo da conta
cast balance ENDERECO --rpc-url RPC_URL

# Verificar contrato
cast call CONTRATO "owner()" --rpc-url RPC_URL

# Backup de logs
cp -r logs/ backups/logs_$(date +%Y%m%d)
```

## 🛡️ Segurança

### Boas Práticas

1. **Chaves Privadas**:
   - Nunca compartilhe suas chaves
   - Use carteiras dedicadas para o bot
   - Mantenha backups seguros

2. **Monitoramento**:
   - Configure alertas Telegram
   - Monitore logs regularmente
   - Verifique health checks

3. **Risk Management**:
   - Defina limites apropriados
   - Use emergency stop se necessário
   - Monitore gas fees

### Emergency Stop

```bash
# Via API
curl -X POST http://localhost:8081/emergency-stop

# Via Docker
docker compose down

# Via logs
# O bot para automaticamente após falhas consecutivas
```

## 📈 Performance

### Otimizações Implementadas

- **Gas Optimization**: Cache de preços e estimativas inteligentes
- **Rate Limiting**: Controle de chamadas API
- **Parallel Processing**: Execução paralela de verificações
- **Smart Caching**: Cache de dados para reduzir latência

### Métricas Típicas

- **Detecção**: ~2-5 segundos por ciclo
- **Execução**: ~10-30 segundos por trade
- **Gas Usage**: ~200k-500k gas por trade
- **Success Rate**: ~70-85% (depende das condições de mercado)

## 🔍 Troubleshooting

### Problemas Comuns

1. **Container não inicia**:
   ```bash
   docker compose logs
   # Verificar configurações no .env
   ```

2. **Health check falha**:
   ```bash
   curl http://localhost:8081/health
   # Verificar se a porta 8081 está livre
   ```

3. **Sem oportunidades detectadas**:
   - Verificar configuração de threshold
   - Verificar conectividade com DEXs
   - Verificar saldo da conta

4. **Trades falhando**:
   - Verificar saldo para gas
   - Verificar limites de slippage
   - Verificar preços de gas

### Logs de Debug

```bash
# Ativar logs verbosos
export LOG_LEVEL=DEBUG
docker compose restart

# Verificar conectividade
curl -I https://base-mainnet.g.alchemy.com/v2/API_KEY
```

## 📊 Estatísticas

### Métricas Coletadas

- Total de oportunidades encontradas
- Total de trades executados
- Taxa de sucesso
- Lucro total
- Gas fees pagos
- Tempo médio de execução

### Dashboard (Opcional)

```bash
# Iniciar com monitoramento
docker compose --profile monitoring up -d

# Acessar Grafana
http://localhost:3000
# User: admin, Pass: admin123
```

## 🤝 Suporte

### Recursos

- **Logs**: Sempre verifique os logs primeiro
- **Health API**: Use para diagnósticos
- **Telegram**: Configure para alertas automáticos

### Contato

- **Issues**: Reporte problemas via logs detalhados
- **Melhorias**: Sugestões são bem-vindas
- **Documentação**: Mantenha este README atualizado

## 📝 Changelog

### v1.0.0 (Atual)
- ✅ Sistema completo de arbitragem
- ✅ Execução automática de trades
- ✅ Risk management avançado
- ✅ Gas optimization
- ✅ Monitoramento completo
- ✅ Docker ready
- ✅ Notificações Telegram

## 📄 Licença

Este projeto é para uso educacional e de pesquisa. Use por sua própria conta e risco.

---

## ⚠️ Disclaimer

**IMPORTANTE**: Trading automatizado envolve riscos significativos. Você pode perder todo o seu investimento. Este bot é fornecido "como está" sem garantias. Sempre teste com pequenas quantias primeiro e monitore constantemente o sistema.

---

*Desenvolvido com ❤️ pela equipe Manus AI*
