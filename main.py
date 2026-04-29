import telebot
import requests
import uuid
import os
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
ACCESS_TOKEN_MP = os.getenv("ACCESS_TOKEN_MP")
RENDER_URL = os.getenv("RENDER_URL")

bot = telebot.TeleBot(TOKEN_TELEGRAM)
app = Flask(__name__)

PLANOS = {
    "1": {"valor": 5.90,  "desc": "Plano Bronze"},
    "2": {"valor": 9.90,  "desc": "Plano Prata"},
    "3": {"valor": 14.90, "desc": "Plano Ouro"},
    "4": {"valor": 20.00, "desc": "Plano VIP Diamond"}
}

@app.route("/")
def home():
    return "Bot rodando!", 200

@app.route(f"/{TOKEN_TELEGRAM}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

@bot.message_handler(commands=["start"])
def enviar_menu(message):
    markup = telebot.types.InlineKeyboardMarkup()
    for id_plano, info in PLANOS.items():
        btn = telebot.types.InlineKeyboardButton(
            f"🎁 {info['desc']} - R$ {info['valor']:.2f}",
            callback_data=f"pix_{id_plano}"
        )
        markup.add(btn)
    bot.send_message(
        message.chat.id,
        "⚡ *ACESSO IMEDIATO* ⚡\n\nEscolha seu plano para liberar os conteúdos agora:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("pix_"))
def callback_pix(call):
    id_plano = call.data.split("_")[1]
    plano = PLANOS[id_plano]
    bot.edit_message_text(
        f"⏳ Gerando seu PIX de R$ {plano['valor']:.2f}... Aguarde.",
        call.message.chat.id,
        call.message.message_id
    )
    url = "https://api.mercadopago.com/v1/payments"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN_MP}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4())
    }
    data = {
        "transaction_amount": plano["valor"],
        "description": plano["desc"],
        "payment_method_id": "pix",
        "payer": {
            "email": f"user_{call.from_user.id}@pagamento.com"
        }
    }
    try:
        res = requests.post(url, json=data, headers=headers)
        res_json = res.json()
        print(f"Resposta MP: {res_json}")
        pix_copia_cola = res_json["point_of_interaction"]["transaction_data"]["qr_code"]
        texto_final = (
            f"✅ *PIX GERADO COM SUCESSO!*\n\n"
            f"💰 *Valor:* R$ {plano['valor']:.2f}\n"
            f"📌 *Plano:* {plano['desc']}\n\n"
            f"👇 *Clique no código abaixo para copiar:*\n\n"
            f"`{pix_copia_cola}`\n\n"
            f"📱 Abra seu banco e use *Pix Copia e Cola*\n\n"
            f"✅ Assim que o pagamento for confirmado, seu acesso será liberado!"
        )
        bot.send_message(call.message.chat.id, texto_final, parse_mode="Markdown")
    except Exception as e:
        print(f"ERRO: {e}")
        print(f"Resposta: {res.text}")
        bot.send_message(call.message.chat.id, "❌ Erro ao gerar PIX. Tente novamente.")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN_TELEGRAM}")
    print(f"✅ Webhook configurado: {RENDER_URL}/{TOKEN_TELEGRAM}")
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
