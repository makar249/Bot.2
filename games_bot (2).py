import asyncio
import os
import random

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

# Усі налаштування беруться зі змінних середовища (Render → Environment)
TOKEN = os.environ["BOT_TOKEN"]
# Посилання на сторінку games.html (обов’язково https://)
GAME_URL = os.environ.get("GAME_URL", "https://example.com/games.html")
# Render сам задає PORT і RENDER_EXTERNAL_URL для Web Service
PORT = int(os.environ.get("PORT", "10000"))
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL")

MENU_TEXT = "Обирай гру:"
MENU_KB = Kb([
    [Btn("🕹 Ігри у вікні", web_app=WebAppInfo(url=GAME_URL))],
    [Btn("✊ Камінь-ножиці-папір", callback_data="r:menu")],
    [Btn("❌ Хрестики-нулики", callback_data="t:new")],
    [Btn("🔢 Вгадай число", callback_data="g:new")],
    [Btn("🎰 Слоти", callback_data="s:spin")],
])
BACK = [Btn("« Меню", callback_data="menu")]


# ---------- Камінь-ножиці-папір ----------
RPS = {"rock": "✊", "scissors": "✌️", "paper": "🖐"}
BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}


def rps_kb():
    return Kb([[Btn(e, callback_data=f"r:{k}") for k, e in RPS.items()], BACK])


async def rps(query, ctx, arg):
    if arg == "menu":
        await query.edit_message_text("Камінь, ножиці чи папір?", reply_markup=rps_kb())
        return
    me, bot = arg, random.choice(list(RPS))
    if me == bot:
        res = "Нічия"
    elif BEATS[me] == bot:
        res = "Ти переміг!"
    else:
        res = "Я переміг"
    await query.edit_message_text(
        f"Ти: {RPS[me]}   Я: {RPS[bot]}\n\n{res}\n\nЩе раз?", reply_markup=rps_kb()
    )


# ---------- Крестики-нолики ----------
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def winner(b):
    for a, c, d in LINES:
        if b[a] and b[a] == b[c] == b[d]:
            return b[a]
    return "draw" if all(b) else None


def bot_move(b):
    empty = [i for i in range(9) if not b[i]]
    for who in ("O", "X"):  # спочатку виграти, потім заблокувати
        for i in empty:
            b[i] = who
            w = winner(b)
            b[i] = ""
            if w == who:
                return i
    if 4 in empty:
        return 4
    return random.choice(empty)


def ttt_kb(b, over):
    sym = {"": "·", "X": "❌", "O": "⭕"}
    rows = []
    for r in range(3):
        rows.append([
            Btn(sym[b[r * 3 + c]], callback_data="noop" if over or b[r * 3 + c] else f"t:{r * 3 + c}")
            for c in range(3)
        ])
    rows.append([Btn("Спочатку", callback_data="t:new")] + BACK)
    return Kb(rows)


async def ttt(query, ctx, arg):
    if arg == "new":
        ctx.user_data["ttt"] = [""] * 9
        await query.edit_message_text("Ти ❌, я ⭕. Ходи!", reply_markup=ttt_kb(ctx.user_data["ttt"], False))
        return
    b = ctx.user_data.get("ttt")
    if not b:
        await ttt(query, ctx, "new")
        return
    i = int(arg)
    if b[i]:
        return
    b[i] = "X"
    w = winner(b)
    if not w:
        b[bot_move(b)] = "O"
        w = winner(b)
    text = {"X": "Ти виграв!", "O": "Я виграв", "draw": "Нічия"}.get(w, "Твій хід")
    await query.edit_message_text(text, reply_markup=ttt_kb(b, bool(w)))


# ---------- Угадай число ----------
def guess_kb():
    rows = [[Btn(str(n), callback_data=f"g:{n}") for n in range(r, r + 5)] for r in (1, 6)]
    rows.append(BACK)
    return Kb(rows)


async def guess(query, ctx, arg):
    if arg == "new":
        ctx.user_data["secret"] = random.randint(1, 10)
        ctx.user_data["tries"] = 3
        await query.edit_message_text("Я загадав число від 1 до 10. У тебе 3 спроби.", reply_markup=guess_kb())
        return
    secret = ctx.user_data.get("secret")
    if secret is None:
        await guess(query, ctx, "new")
        return
    n = int(arg)
    ctx.user_data["tries"] -= 1
    left = ctx.user_data["tries"]
    again = Kb([[Btn("Ще раз", callback_data="g:new")], BACK])
    if n == secret:
        ctx.user_data["secret"] = None
        await query.edit_message_text(f"Вгадав, це {secret}!", reply_markup=again)
    elif left == 0:
        ctx.user_data["secret"] = None
        await query.edit_message_text(f"Спроби закінчилися. Я загадав {secret}.", reply_markup=again)
    else:
        hint = "більше" if secret > n else "менше"
        await query.edit_message_text(
            f"Не {n}. Загадане число {hint}. Залишилось спроб: {left}", reply_markup=guess_kb()
        )


# ---------- Слоти ----------
async def slots(query, ctx, arg):
    await query.answer()
    msg = await query.message.reply_dice(emoji="🎰")
    await asyncio.sleep(3.5)
    v = msg.dice.value
    if v == 64:
        text = "Джекпот! Три сімки 🎉"
    elif v in (1, 22, 43):
        text = "Три однакових, ти виграв!"
    else:
        text = "Не пощастило. Крутимо ще?"
    await query.message.reply_text(text, reply_markup=Kb([[Btn("🎰 Ще раз", callback_data="s:spin")], BACK]))


# ---------- Общее ----------
GAMES = {"r": rps, "t": ttt, "g": guess, "s": slots}


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(MENU_TEXT, reply_markup=MENU_KB)


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "noop":
        await query.answer()
        return
    if data == "menu":
        await query.answer()
        await query.edit_message_text(MENU_TEXT, reply_markup=MENU_KB)
        return
    game, arg = data.split(":", 1)
    if game != "s":
        await query.answer()
    await GAMES[game](query, ctx, arg)


def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler(["start", "games"], start))
    app.add_handler(CallbackQueryHandler(on_button))

    if BASE_URL:
        # Render: вебхук (сервіс слухає порт і прокидається від запитів Telegram)
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{BASE_URL.rstrip('/')}/{TOKEN}",
            drop_pending_updates=True,
        )
    else:
        # Локальний запуск без Render
        app.run_polling()


if __name__ == "__main__":
    main()
