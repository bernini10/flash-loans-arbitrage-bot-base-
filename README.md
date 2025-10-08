# Flash Loans Arbitrage Bot 🚀

Bot automatizado para detecção e execução de oportunidades de arbitragem usando flash loans na rede Base.

## 🔧 Características

- **Monitoramento em tempo real** de preços em múltiplas DEXs
- **Rate limiting inteligente** para evitar bloqueios de API
- **Notificações Telegram** para oportunidades encontradas
- **Health checks** e monitoramento de status
- **Containerização Docker** para deploy fácil
- **Logging estruturado** para debugging

## 🏗 Arquitetura

### DEXs Monitoradas
- Uniswap V3
- SushiSwap V3  
- Aerodrome

### Tokens Suportados
- WETH (Wrapped Ethereum)
- USDC (USD Coin)

## 🚀 Instalação e Uso

### Pré-requisitos
- Docker e Docker Compose
- Conta Telegram e bot token
- Chave API da Alchemy
- Carteira com private key

### 1. Configuração

```bash
# Clonar repositório
git clone https://github.com/bernini10/flash-loans-arbitrage-bot-base-.git
cd flash-loans-arbitrage-bot-base-

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas configurações
```

### 2. Execução com Docker (Recomendado)

```bash
# Construir e executar
./start.sh docker

# Ou manualmente
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar
docker-compose down
```

### 3. Execução Local

```bash
# Instalar dependências
pip install -r requirements.txt
npm install

# Executar
./start.sh local
```

### 4. Com Monitoramento (Prometheus + Grafana)

```bash
./start.sh monitoring

# Acessar dashboards
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

## 📊 Monitoramento

### Health Check
```bash
curl http://localhost:8080/health
```

### Estatísticas
```bash
curl http://localhost:8080/stats
```

## ⚙️ Configuração

### Variáveis de Ambiente (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Blockchain
ALCHEMY_API_KEY=your_api_key
PRIVATE_KEY=your_private_key

# Bot Settings
MIN_PROFIT_THRESHOLD=0.005  # 0.5% mínimo
MAX_GAS_PRICE=50           # 50 gwei máximo
API_CALL_DELAY=2           # 2 segundos entre calls
CYCLE_DELAY=300            # 5 minutos entre ciclos
```

### Configuração do Telegram

1. Criar bot com @BotFather
2. Obter token do bot
3. Obter chat ID enviando mensagem para @userinfobot

## 🔒 Segurança

- **Nunca** commitar arquivos `.env`
- Usar carteiras dedicadas com fundos limitados
- Monitorar logs regularmente
- Implementar stop-loss automático

## 📈 Performance

### Rate Limiting
- 2 segundos entre chamadas de API
- 5 minutos entre ciclos completos
- Retry automático com backoff

### Otimizações
- Multi-stage Docker build
- Cache de contratos
- Logging assíncrono
- Health checks automáticos

## 🐛 Troubleshooting

### Erros Comuns

**"Could not transact with/call contract"**
- Verificar se os endereços dos contratos estão corretos
- Confirmar conectividade com a rede Base
- Validar API key da Alchemy

**Rate Limiting (429 errors)**
- Aumentar `API_CALL_DELAY` no .env
- Verificar limites da API da Alchemy

**Telegram não funciona**
- Verificar token e chat ID
- Confirmar que o bot foi iniciado no Telegram

### Logs

```bash
# Docker
docker-compose logs -f flash-arbitrage-bot

# Local
tail -f logs/arbitrage_bot.log
```

## 📚 Estrutura do Projeto

```
├── contracts/              # Smart contracts Solidity
├── src/                   # Código fonte Python
├── logs/                  # Arquivos de log
├── monitoring/            # Configurações Prometheus/Grafana
├── Dockerfile            # Configuração Docker
├── docker-compose.yml    # Orquestração de serviços
├── start.sh             # Script de inicialização
└── opportunity_monitor_improved.py  # Monitor principal
```

## 🤝 Contribuição

1. Fork o projeto
2. Criar branch para feature (`git checkout -b feature/nova-feature`)
3. Commit mudanças (`git commit -am 'Adicionar nova feature'`)
4. Push para branch (`git push origin feature/nova-feature`)
5. Abrir Pull Request

## ⚠️ Disclaimer

Este bot é para fins educacionais. Trading automatizado envolve riscos. Use por sua própria conta e risco.

## 📄 Licença

MIT License - veja arquivo [LICENSE](LICENSE) para detalhes.

---

**Desenvolvido com ❤️ para a comunidade DeFi**
