import requests
import os

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, message):
        url = f"{self.base_url}/sendMessage"
        params = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(url, json=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending Telegram message: {e}")
            return None

    def format_arbitrage_opportunity(self, opportunity):
        message = (
            f"*Nova Oportunidade de Arbitragem!*\n\n"
            f"*Token A:* `{opportunity['tokenA']}`\n"
            f"*Token B:* `{opportunity['tokenB']}`\n"
            f"*DEX de Compra:* `{opportunity['dexBuy']}`\n"
            f"*DEX de Venda:* `{opportunity['dexSell']}`\n"
            f"*Valor do Empréstimo:* `{opportunity['amountIn']}`\n"
            f"*Lucro Estimado (BPS):* `{opportunity['minProfitBps']}`\n"
            f"*Deadline:* `{opportunity['deadline']}`\n"
        )
        return message

    def send_arbitrage_opportunity(self, opportunity):
        message = self.format_arbitrage_opportunity(opportunity)
        return self.send_message(message)

