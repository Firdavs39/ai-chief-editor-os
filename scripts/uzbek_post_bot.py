"""uzbek_post_bot.py — простой бот: кидаешь пост → узбекская версия → «Опубликовать».

Поток:
  1. Открываешь @buaiuz_bot в Telegram, шлёшь/пересылаешь любой пост (текст).
  2. Бот за ~20-40 сек переделывает его на узбекский (латиница) через Kimi.
  3. Присылает узбекскую версию + кнопки «✅ Опубликовать» / «❌ Отмена».
  4. Жмёшь «Опубликовать» → бот постит в твой канал.

НИКАКИХ новых ключей: bot_token, целевой канал и Kimi берутся из уже
настроенного Vault (как и весь остальной проект). НЕ нужен api_id / api_hash /
номер телефона — это всё для чтения чужих каналов (Telethon), а тут обычный бот.

Запуск (PowerShell, из корня проекта):
    cd C:\\Users\\user\\ai-chief-editor-os
    $env:PYTHONPATH="packages/shared;apps/api;apps/worker"
    python scripts/uzbek_post_bot.py

Безопасность: бот отвечает ТОЛЬКО владельцу. Если TELEGRAM_OWNER_ID не задан,
первый, кто напишет боту, становится владельцем на эту сессию, и бот подскажет,
как закрепить его навсегда. Публикация — только по нажатию кнопки (ты сам
подтверждаешь каждый пост). Автопостинга нет.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from chief_editor.llm.registry import get_llm_provider
from chief_editor.services.integration_config import resolve_provider
from chief_editor.settings import get_settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger("uzbek_bot")

# --- конфиг из Vault (никаких ручных ключей) ---
_tg = resolve_provider("telegram_bot")
BOT_TOKEN = (_tg["bot_token"].value or "").strip()
CHANNEL = (_tg["target_channel_id"].value or "").strip()
OWNER_ID = (get_settings().telegram_owner_id or "").strip()

# Узбекский «переписыватель»: не перевод, а адаптация под узбекскую аудиторию.
SYSTEM = (
    "Sen tajribali AI-blogeri, Telegram kanali muallifisan. Senga rus yoki ingliz "
    "tilidagi post beriladi. Uni o'zbek tiliga (lotin alifbosida) tabiiy, jonli va "
    "qiziqarli qilib qayta yoz — quruq tarjima emas, balki o'zbek auditoriyasi uchun "
    "moslashtir. Birinchi jumla e'tiborni tortsin. AI-shtamplarsiz, sun'iy "
    "iboralarsiz, ortiqcha kalkasiz. Faqat tayyor postni JSON sifatida qaytar."
)
_SCHEMA = {
    "type": "object",
    "required": ["text"],
    "properties": {"text": {"type": "string"}},
}

# Переделанный текст между сообщением и нажатием кнопки (по user_id).
_pending: dict[int, str] = {}
# Владелец сессии, если TELEGRAM_OWNER_ID не задан в .env.
_session_owner: dict[str, int] = {}


def _is_owner(user_id: int) -> bool:
    if OWNER_ID:
        return str(user_id) == OWNER_ID
    if "id" not in _session_owner:
        _session_owner["id"] = user_id  # первый написавший = владелец сессии
    return _session_owner["id"] == user_id


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None or update.effective_user is None:
        return
    user_id = update.effective_user.id
    if not _is_owner(user_id):
        return  # чужих игнорируем

    if not OWNER_ID and _session_owner.get("id") == user_id:
        log.info("session owner = %s (set TELEGRAM_OWNER_ID to lock permanently)", user_id)

    src = (msg.text or msg.caption or "").strip()
    if not src:
        await msg.reply_text("Matnli post yuboring (matn yoki izohli rasm).")
        return

    note = ""
    if not OWNER_ID:
        note = f"\n\n(Botni o'zingizga biriktirish uchun .env ga qo'ying: TELEGRAM_OWNER_ID={user_id})"
    await msg.reply_text("⏳ O'zbekchaga o'giryapman, biroz kuting…" + note)

    try:
        provider = get_llm_provider()
        result = provider.complete_json(
            system=SYSTEM, user=src, schema=_SCHEMA, temperature=0.6
        )
        uz = (result.get("text") or "").strip()
    except Exception as exc:  # noqa: BLE001 — surface a friendly error
        log.exception("rework failed")
        await msg.reply_text(f"❌ Xatolik: {type(exc).__name__}. Qayta urinib ko'ring.")
        return

    if not uz:
        await msg.reply_text("❌ Bo'sh natija. Qayta yuboring.")
        return

    _pending[user_id] = uz
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data="pub"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
            ]
        ]
    )
    await msg.reply_text(uz, reply_markup=kb)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q is None or q.from_user is None:
        return
    user_id = q.from_user.id
    if not _is_owner(user_id):
        await q.answer("Ruxsat yo'q")
        return
    await q.answer()

    if q.data == "cancel":
        _pending.pop(user_id, None)
        await q.edit_message_text("❌ Bekor qilindi.")
        return

    text = _pending.pop(user_id, None)
    if not text:
        await q.edit_message_text("Matn topilmadi — postni qaytadan yuboring.")
        return

    try:
        await context.bot.send_message(chat_id=CHANNEL, text=text)
    except Exception as exc:  # noqa: BLE001
        log.exception("publish failed")
        await q.edit_message_text(f"❌ Joylashda xatolik: {type(exc).__name__}")
        return

    await q.edit_message_text("✅ Kanalga joylandi!\n\n" + text)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Нет bot_token в Vault. Добавь через /secrets/telegram_bot.")
    if not CHANNEL:
        raise SystemExit("Нет target_channel_id в Vault (например -1003980277723).")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, on_message))
    app.add_handler(CallbackQueryHandler(on_button))
    log.info("Бот запущен. Открой @buaiuz_bot и пришли пост. Канал: %s", CHANNEL)
    app.run_polling()


if __name__ == "__main__":
    main()
