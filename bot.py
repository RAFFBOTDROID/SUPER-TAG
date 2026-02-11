import logging
import sqlite3
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import httpx

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
INVISIVEL = "⠀"

logging.basicConfig(level=logging.INFO)

# ================= BANCO =================
def db():
    return sqlite3.connect("/tmp/bot_tags.db")

def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS canais (
            chat_id INTEGER PRIMARY KEY,
            ativo INTEGER DEFAULT 1,
            texto_inicio TEXT DEFAULT '',
            texto_fim TEXT DEFAULT '',
            tags_inicio TEXT DEFAULT '',
            tags_fim TEXT DEFAULT '',
            botao_texto TEXT DEFAULT '',
            botao_link TEXT DEFAULT '',
            ia_auto INTEGER DEFAULT 0,
            auto_post INTEGER DEFAULT 0,
            espacamento INTEGER DEFAULT 2
        )
        """)

def get_cfg(chat_id):
    with db() as con:
        return con.execute(
            "SELECT * FROM canais WHERE chat_id=?",
            (chat_id,)
        ).fetchone()

def set_cfg(chat_id, campo, valor):
    with db() as con:
        con.execute(
            f"UPDATE canais SET {campo}=? WHERE chat_id=?",
            (valor, chat_id)
        )

def reset_cfg(chat_id):
    with db() as con:
        con.execute("""
        UPDATE canais SET
        texto_inicio='',
        texto_fim='',
        tags_inicio='',
        tags_fim='',
        botao_texto='',
        botao_link='',
        ia_auto=0,
        auto_post=0,
        espacamento=2
        WHERE chat_id=?
        """, (chat_id,))

def delete_cfg(chat_id):
    with db() as con:
        con.execute("DELETE FROM canais WHERE chat_id=?", (chat_id,))

def all_canais():
    with db() as con:
        return con.execute("SELECT chat_id FROM canais").fetchall()

# ================= MENU =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Meus canais / grupos", callback_data="canais")]
    ])
    await update.message.reply_text(
        "🤖 **Bot de Tags Inteligente**\n\n"
        "✨ Edita posts automaticamente\n"
        "🖼 Texto, imagem, vídeo, música\n"
        "⚙️ Totalmente configurável\n\n"
        "👉 Adicione como ADMIN e poste algo.",
        reply_markup=teclado,
        parse_mode="Markdown"
    )

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "canais":
        canais = all_canais()
        if not canais:
            await q.message.reply_text("❌ Nenhum canal registrado.")
            return
        teclado = [[InlineKeyboardButton(f"📌 Chat {c[0]}", callback_data=f"cfg:{c[0]}")] for c in canais]
        await q.message.reply_text("📢 **Selecione um canal**", reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown")
        return

    if data.startswith("cfg:"):
        chat_id = int(data.split(":")[1])
        context.user_data["chat_id"] = chat_id
        cfg = get_cfg(chat_id)
        ia_auto = cfg[8] if cfg else 0
        auto_post = cfg[9] if cfg else 0
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏ Texto inicial", callback_data="ti"), InlineKeyboardButton("✏ Texto final", callback_data="tf")],
            [InlineKeyboardButton("🏷 Tags início", callback_data="tgi"), InlineKeyboardButton("🏷 Tags fim", callback_data="tgf")],
            [InlineKeyboardButton("🔘 Botão texto", callback_data="bt"), InlineKeyboardButton("🔗 Botão link", callback_data="bl")],
            [InlineKeyboardButton("↕ Espaçamento", callback_data="esp")],
            [InlineKeyboardButton(f"🤖 IA automática {'✅' if ia_auto else '⛔'}", callback_data="ia_auto")],
            [InlineKeyboardButton(f"📤 Auto-post {'✅' if auto_post else '⛔'}", callback_data="auto_post")],
            [InlineKeyboardButton("♻ Resetar dados", callback_data="reset")],
            [InlineKeyboardButton("🗑 Remover canal", callback_data="delete")]
        ])
        await q.message.reply_text(f"⚙️ **Configuração do chat {chat_id}**", reply_markup=teclado, parse_mode="Markdown")
        return

    if data in {"ti","tf","tgi","tgf","bt","bl","esp"}:
        context.user_data["edit"] = data
        msg = "✍️ Envie o texto:" if data != "esp" else "↕ Envie um número (0 a 5):"
        await q.message.reply_text(msg)
        return

    chat_id = context.user_data.get("chat_id")

    if data == "ia_auto":
        cfg = get_cfg(chat_id)
        novo = 0 if cfg[8] == 1 else 1
        set_cfg(chat_id, "ia_auto", novo)
        await q.message.reply_text("🤖 IA automática ✅" if novo else "⛔ IA automática")

    if data == "auto_post":
        cfg = get_cfg(chat_id)
        novo = 0 if cfg[9] == 1 else 1
        set_cfg(chat_id, "auto_post", novo)
        await q.message.reply_text("📤 Auto-post ✅" if novo else "⛔ Auto-post")

    if data == "reset":
        reset_cfg(chat_id)
        await q.message.reply_text("♻ Dados resetados com sucesso!")

    if data == "delete":
        delete_cfg(chat_id)
        await q.message.reply_text("🗑 Canal removido do bot!")

# ================= RECEBER TEXTO =================
async def receber_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "edit" not in context.user_data:
        return
    chat_id = context.user_data.get("chat_id")
    campo = context.user_data.pop("edit")
    texto = update.message.text
    mapa = {"ti": "texto_inicio","tf": "texto_fim","tgi": "tags_inicio","tgf": "tags_fim","bt": "botao_texto","bl": "botao_link","esp": "espacamento"}
    if campo == "esp":
        if not texto.isdigit() or int(texto) > 5:
            await update.message.reply_text("❌ Envie um número de 0 a 5.")
            return
        texto = int(texto)
    set_cfg(chat_id, mapa[campo], texto)
    await update.message.reply_text("✅ Salvo com sucesso!")

# ================= GROQ FULL LOGGING =================
async def gerar_texto_groq(prompt):
    url = "https://api.groq.ai/v1/generate"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    data = {"model": "groq-text-mini", "prompt": prompt, "max_output_tokens": 150}
    for tentativa in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=data)
                if resp.status_code == 200:
                    output = resp.json().get("output_text", "")
                    logging.info(f"✅ Groq OK: {output}")
                    return output
                else:
                    logging.error(f"❌ Groq HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logging.error(f"❌ Groq tentativa {tentativa+1} falhou: {e}")
        await asyncio.sleep(2)
    return "🤖 Erro ao gerar texto (ver logs Worker para detalhes)"

# ================= PROCESSAR POSTS =================
async def processar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post or update.message
    if not msg or not msg.chat:
        return
    chat_id = msg.chat.id
    with db() as con:
        con.execute("INSERT OR IGNORE INTO canais (chat_id) VALUES (?)", (chat_id,))
    cfg = get_cfg(chat_id)
    if not cfg or cfg[1] == 0:
        return
    _, _, ti, tf, tgi, tgf, bt, bl, ia_auto, auto_post, esp = cfg
    sep = "\n" * esp
    texto = msg.text or msg.caption or INVISIVEL
    if ia_auto or auto_post:
        prompt = f"Gere um post completo sobre: {texto}"
        texto_gerado = await gerar_texto_groq(prompt)
        logging.info(f"🔹 Texto gerado para canal {chat_id}: {texto_gerado}")
        texto = texto_gerado or texto
    inicio = f"{ti}{sep}{tgi}{sep}" if ti or tgi else ""
    fim = f"{sep}{tgf}{sep}{tf}" if tf or tgf else ""
    texto_final = inicio + texto + fim
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton(bt, url=bl)]]) if bt and bl else None
    try:
        if msg.text:
            await msg.edit_text(texto_final, reply_markup=teclado)
        else:
            await msg.edit_caption(texto_final, reply_markup=teclado)
    except Exception as e:
        logging.error(f"❌ Erro ao editar: {e}")

# ================= MAIN =================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, receber_texto))
    app.add_handler(MessageHandler(
        filters.ChatType.CHANNEL | filters.ChatType.GROUP | filters.ChatType.SUPERGROUP,
        processar
    ))
    print("🤖 Bot rodando no Koyeb (Groq full logging)...")
    app.run_polling()

if __name__ == "__main__":
    main()
