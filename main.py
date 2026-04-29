import telebot
import requests
import uuid
import os
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")
ACCESS_TOKEN_ABACATE = os.getenv("ACCESS_TOKEN_ABACATE")
RENDER_URL = os.getenv("RENDER_URL")

bot = telebot.TeleBot(TOKEN_TELEGRAM)
app = Flask(__name__)

PLANOS = {
    "1": {"valor": 590,  "desc": "Plano Bronze"},
    "2": {"valor": 990,  "desc": "Plano Prata"},
    "3": {"valor": 1490, "desc": "Plano Ouro"},
    "4": {"valor": 2000, "desc": "Plano VIP Diamond"}
}

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN_ABACATE}",
    "Content-Type": "application/json"
}

def criar_ou_buscar_cliente(user_id, nome):
    # Tenta criar o cliente
    url = "https://api.abacatepay.com/v1/customer/create"
    data = {
        "name": nome if nome else f"Cliente {user_id}",
        "email": f"user_{user_id}@pagamento.com",
        "cellphone": "11999999999",
        "taxId": "529.982.247-25"
    }
    res = requests.post(url, json=data, headers=HEADERS).json()
    print(f"Criar cliente: {res}")

    if res.get("success"):
        return res["data"]["id"]

    # Se falhou, busca na lista
    lista = requests.get("https://api.abacatepay.com/v1/customer/list", headers=HEADERS).json()
    print(f"Lista clientes: {lista}")
    if lista.get("success"):
        for c in lista["data"]:
            if f"user_{user_id}" in c.get("metadata", {}).get("email", ""):
                return c["id"]
    return None

def criar_cobranca(customer_id, customer_data, plano_id, valor, desc):
    url = "https://api.abacatepay.com/v1/billing/create"
    data = {
        "amount": valor,
        "methods": ["PIX"],
        "externalId": str(uuid.uuid4()),
        "frequency": "ONE_TIME",
        "customer": {
            "id": customer_id,
            "name": customer_data["name"],
            "email": customer_data["email"],
            "cellphone": customer_data["cellphone"],
            "taxId": customer_data["taxId"]
        },
        "products": [
            {
                "externalId": f"plano{plano_id}",
                "name": desc,
                "quantity": 1,
                "price": valor
            }
        ],
        "returnUrl": RENDER_URL,
        "completionUrl": RENDER_URL
    }
    res = requests.post(url, json=data, headers=HEADERS).json()
    print(f"Criar cobranca: {res}")
    return res

@app.route("/")
def home():
    return "Bot rodando!", 200

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
    bot.send_message(
        message.chat.id,
        "⚡ *ACESSO IMEDIATO* ⚡\n\nEscolha seu plano para liberar os conteúdos agora:",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("aba_"))
def callback_abacate(call):
    id_plano = call.data.split("_")[1]
    plano = PLANOS[id_plano]
    user_id = call.from_user.id
    nome = call.from_user.first_name or f"Cliente {user_id}"

    bot.edit_message_text(
        f"⏳ Gerando PIX de R$ {plano['valor']/100:.2f}... Aguarde.",
        call.message.chat.id,
        call.message.message_id
    )

    try:
        # Criar ou buscar cliente
        customer_id = criar_ou_buscar_cliente(user_id, nome)
        if not customer_id:
            raise Exception("Nao foi possivel criar o cliente")

        customer_data = {
            "name": nome,
            "email": f"user_{user_id}@pagamento.com",
            "cellphone": "11999999999",
            "taxId": "529.982.247-25"
        }

        # Criar cobranca
        res = criar_cobranca(customer_id, customer_data, id_plano, plano["valor"], plano["desc"])

        if not res.get("success"):
            raise Exception(f"Erro ao criar cobranca: {res}")

        checkout_url = res["data"]["url"]

        texto = (
            f"✅ *PAGAMENTO GERADO!*\n\n"
            f"💰 *Valor:* R$ {plano['valor']/100:.2f}\n"
            f"📌 *Plano:* {plano['desc']}\n\n"
            f"👇 Clique no botão abaixo para pagar via PIX:"
        )

        markup = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton("💳 PAGAR AGORA", url=checkout_url)
        markup.add(btn)

        bot.send_message(call.message.chat.id, texto, parse_mode="Markdown", reply_markup=markup)

    except Exception as e:
        print(f"ERRO: {e}")
        bot.send_message(call.message.chat.id, "❌ Erro ao gerar pagamento. Tente novamente.")

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{TOKEN_TELEGRAM}")
    print(f"✅ Webhook configurado!")
    porta = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=porta)
