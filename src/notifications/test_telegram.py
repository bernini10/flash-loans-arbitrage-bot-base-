import os
from telegram_notifier import TelegramNotifier

# Set environment variables for testing
os.environ['TELEGRAM_BOT_TOKEN'] = '7743586944:AAHLoX4pWPMd_lsN55TBuS22u0vW-c3uofE'
os.environ['TELEGRAM_CHAT_ID'] = '918968963'

if __name__ == "__main__":
    notifier = TelegramNotifier()
    test_opportunity = {
        'tokenA': '0xTokenAAddress',
        'tokenB': '0xTokenBAddress',
        'dexBuy': '0xDexBuyAddress',
        'dexSell': '0xDexSellAddress',
        'amountIn': '1000',
        'minProfitBps': '50',
        'deadline': '1672531199'
    }
    
    # Test sending a simple message
    print("Sending test message...")
    response = notifier.send_message("Olá! Este é um teste do sistema de notificações do bot de arbitragem.")
    if response and response.get('ok'):
        print("Test message sent successfully!")
    else:
        print("Failed to send test message.")
        if response:
            print(f"Response: {response}")

    # Test sending a formatted opportunity
    print("\nSending formatted opportunity...")
    response = notifier.send_arbitrage_opportunity(test_opportunity)
    if response and response.get('ok'):
        print("Formatted opportunity sent successfully!")
    else:
        print("Failed to send formatted opportunity.")
        if response:
            print(f"Response: {response}")

