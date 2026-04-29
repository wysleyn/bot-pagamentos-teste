import telebot
import requests
import uuid
import os
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
ACCESS_TOKEN_ABACATE = os.getenv("ACCESS_TOKEN_ABACATE") # Mudei o nome da variavel
RENDER_URL = os.getenv("RENDER_URL")

bot = telebot.TeleBot(TOKEN_TELEGRAM)
app = Flask(__name__)

PLANOS = {
    "1": {"valor": 590,  "desc": "Plano Bronze"},    # AbacatePay usa centavos (590 = R$ 5,90)
    "2": {"valor": 990,  "desc": "Plano Prata"},
    "3": {"valor": 1490, "desc": "Plano Ouro"},
    "4": {"valor": 2000, "desc": "Plano VIP Diamond"}
}

@app.route("/")
def home():
    return "Bot AbacatePay rodando!", 200

@app.route(f"/{TOKEN_TELEGRAM}", methods=["POST"])
def webhook_telegram():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

@bot.message_handler(commands=["start"])
def enviar_menu(message):
    markup = telebot.types.InlineKeyboardMarkup()
    for id_plano, info in PLANOS.items():
        btn = telebot.types.InlineKeyboardButton(
            f"🎁 {info['desc']} - R$ {info['valor']/100:.2f}",
            callback_data=f"aba_{id_plano}"
        )
        markup.add(btn)
    bot.send_message(message.chat.id, "🔞 **ESCOLHA SEU PLANO** 🔞\n\nO PIX é gerado na hora!", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("aba_"))
def callback_abacate(call):
    id_plano = call.data.split("_")[1]
    plano = PLANOS[id_plano]
    bot.edit_message_text(f"⏳ Gerando PIX de R$ {plano['valor']/100:.2f}...", call.message.chat.id, call.message.message_id)

    url = "https://api.abacatepay.com/v1/billing/create"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN_ABACATE}",
        "Content-Type": "application/json"
    }
    
    data = {
        "amount": plano["valor"],
        "methods": ["pix"],
        "customerId": f"user_{call.from_user.id}", # ID do cliente no AbacatePay
        "externalId": str(uuid.uuid4()),
        "returnUrl": RENDER_URL,
        "completionUrl": RENDER_URL
    }

    try:
        # Primeiro tentamos criar a cobrança
        res = requests.post(url, json=data, headers=headers).json()
        print(f"Resposta AbacatePay: {res}")
        
        # A AbacatePay v1 geralmente retorna um link de checkout
        # Vamos pegar o link de pagamento
        checkout_url = res['data']['url']
        
        texto_final = (
            f"✅ *PAGAMENTO PRONTO!*\n\n"
            f"💰 *Valor:* R$ {plano['valor']/100:.2f}\n"
            f"📌 *Plano:* {plano['desc']}\n\n"
            f"Clique no botão abaixo para abrir o PIX Copia e Cola:"
        )
        
        markup = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton("🔗 ABRIR PIX", url=checkout_url)
        markup.add(btn)
        
        bot.send_message(call.message.chat.id, texto_final, parse_mode="Markdown", reply_markup=markup)
        
    except Exception as e:
        print(f"ERRO: {e}")
        bot.send_message(call.message.chat.id, "❌ Erro ao gerar PIX. Tente novamente.")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN_TELEGRAM}")
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
