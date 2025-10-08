# Multi-stage build para otimizar o tamanho da imagem
FROM node:18-alpine AS node-builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js
COPY --from=node-builder /usr/local/bin/node /usr/local/bin/
COPY --from=node-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# Configurar diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY requirements.txt package*.json ./

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar dependências Node.js
COPY --from=node-builder /app/node_modules ./node_modules

# Copiar código fonte
COPY . .

# Criar usuário não-root para segurança
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Expor porta para monitoramento (opcional)
EXPOSE 8080

# Comando padrão
CMD ["python3", "opportunity_monitor.py"]
