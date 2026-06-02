"""uzbek_post_bot.py — умный бот: кидаешь пост → красивая узбекская версия → «Опубликовать».

Поток:
  1. Открываешь @buaiuz_bot, шлёшь/пересылаешь пост (текст, или видео/фото с текстом).
  2. Бот делает УМНУЮ переделку под канал @buai_uz:
       • вырезает чужое: рекламу другого канала, их @упоминания, хештеги, ссылки,
         их «подпишитесь на нас» — всё, что не наш контент;
       • переписывает суть на живой узбекский (латиница);
       • красиво оформляет: эмодзи к месту, разбивка, жирный для важного;
       • сам подбирает 2-4 хештега по теме;
       • контекстно вписывает @buai_uz (не один и тот же шаблон).
  3. Если был видео/фото — он сохраняется, узбекский текст идёт подписью.
  4. Присылает версию + кнопки «✅ Опубликовать» / «❌ Отмена».
  5. Жмёшь «Опубликовать» → постит в канал. Автопостинга нет — только по кнопке.

Ключи (bot_token, канал, Kimi) — из уже настроенного Vault. Запуск:
    cd C:\\Users\\user\\ai-chief-editor-os
    $env:PYTHONPATH="packages/shared;apps/api;apps/worker"
    python scripts/uzbek_post_bot.py
"""
from __future__ import annotations

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
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

_tg = resolve_provider("telegram_bot")
BOT_TOKEN = (_tg["bot_token"].value or "").strip()
CHANNEL = (_tg["target_channel_id"].value or "").strip()
OWNER_ID = (get_settings().telegram_owner_id or "").strip()

# Telegram-овые лимиты
CAPTION_LIMIT = 1024  # подпись к медиа
TEXT_LIMIT = 4096  # обычное сообщение

# Умный редактор канала @buai_uz. Вся «сообразительность» — здесь.
SYSTEM = (
    "Sen @buai_uz Telegram kanalining tajribali AI-muharririsan. Kanal AI va "
    "texnologiyalar haqida, auditoriya — oʻzbek tilidagi yoshlar, dasturchilar, "
    "texnologiya ixlosmandlari.\n\n"
    "Senga BOSHQA manbadan post beriladi (rus yoki ingliz tilida). Vazifang — uni "
    "@buai_uz uchun CHIROYLI oʻzbekcha postga aylantirish.\n\n"
    "QATʼIY QOIDALAR:\n"
    "1. BEGONA NARSANI OLIB TASHLA: boshqa kanal reklamasi, ularning kanal "
    "nomlari va @username-lari, ularning 'obuna boʻling' chaqiriqlari, ularning "
    "heshteglari va havolalari — BARCHASINI oʻchir. Bu bizning kontent emas.\n"
    "2. MATNNI TOʻLIQ SAQLA: postning BUTUN mazmunini oʻzbekchaga oʻgir — "
    "QISQARTIRMA, gʻoyalar, tafsilotlar, raqamlar va abzatslarni tashlab ketma. "
    "Postning hajmi va toʻliqligi originalga mos boʻlsin. FAQAT begona reklama/"
    "promo olib tashlanadi, qolgan HAMMA maʼlumot toʻliq qoladi. Hech narsa "
    "oʻylab topma, lekin hech narsani ham qisqartirma.\n"
    "3. OʻZBEKCHA (lotin) tabiiy, jonli til. Quruq tarjima emas, lekin mazmunni "
    "toʻliq saqlagan holda. Birinchi jumla eʼtiborni tortsin.\n"
    "4. CHIROYLI BEZA — skuchli va tussiz EMAS:\n"
    "   • emojilardan oʻrinli foydalan (mazmunga mos, har qatorda emas);\n"
    "   • qatorlarga ajrat, oʻqish oson boʻlsin;\n"
    "   • eng muhim joyni <b>qalin</b> bilan belgila (Telegram HTML: faqat "
    "<b>, <i> teglari, boshqasi yoʻq);\n"
    "5. HESHTEG: mavzuga mos 2-4 ta heshteg OʻZING tanlab, oxiriga qoʻsh.\n"
    "6. @buai_uz ni tabiiy joyla — har doim bir xil shior emas, postga mos "
    "ravishda (oxirida imzo sifatida yoki matn ichida).\n\n"
    "Format qatʼiy shablon EMAS — har bir postga mos ravishda oʻzgartir.\n"
    "Faqat tayyor postni JSON qaytar: {\"post\": \"<HTML bilan tayyor post>\"}. "
    "Boshqa hech narsa yozma."
)
_SCHEMA = {
    "type": "object",
    "required": ["post"],
    "properties": {"post": {"type": "string"}},
}

# Ожидающие публикации черновики (по user_id): текст + медиа.
_pending: dict[int, dict] = {}
_session_owner: dict[str, int] = {}


def _is_owner(user_id: int) -> bool:
    if OWNER_ID:
        return str(user_id) == OWNER_ID
    if "id" not in _session_owner:
        _session_owner["id"] = user_id
    return _session_owner["id"] == user_id


def _media_of(msg) -> tuple[str | None, str | None]:
    """Returns (kind, file_id) for a photo/video message, else (None, None)."""
    if msg.photo:
        return "photo", msg.photo[-1].file_id  # largest size
    if msg.video:
        return "video", msg.video.file_id
    if msg.animation:
        return "animation", msg.animation.file_id
    return None, None


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and not _is_owner(update.effective_user.id):
        return
    await update.message.reply_text(
        "Салом! Кинь мне любой пост (текст, или видео/фото с подписью) — я "
        "переделаю его на узбекский для @buai_uz: вырежу чужую рекламу, красиво "
        "оформлю с эмодзи, добавлю хештеги и нашу подпись. Покажу с кнопками — "
        "опубликую только когда сам нажмёшь «Опубликовать»."
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None or update.effective_user is None:
        return
    user_id = update.effective_user.id
    if not _is_owner(user_id):
        return

    src = (msg.text or msg.caption or "").strip()
    kind, file_id = _media_of(msg)

    if not src:
        if kind:
            await msg.reply_text("Пришли пост С ТЕКСТОМ (подписью) — голое медиа переделывать нечего.")
        else:
            await msg.reply_text("Пришли текстовый пост — переделаю на узбекский.")
        return

    note = ""
    if not OWNER_ID:
        note = f"\n\n(Закрепить бота за собой: добавь в .env  TELEGRAM_OWNER_ID={user_id})"
    media_note = f" (с {kind})" if kind else ""
    await msg.reply_text(f"⏳ Переделываю на узбекский{media_note}…" + note)

    try:
        provider = get_llm_provider()
        result = provider.complete_json(
            system=SYSTEM, user=src, schema=_SCHEMA, temperature=0.6
        )
        uz = (result.get("post") or "").strip()
    except Exception as exc:  # noqa: BLE001
        log.exception("rework failed")
        await msg.reply_text(f"❌ Хатолик: {type(exc).__name__}. Попробуй ещё раз.")
        return

    if not uz:
        await msg.reply_text("❌ Пустой результат. Попробуй ещё раз.")
        return

    _pending[user_id] = {"text": uz, "kind": kind, "file_id": file_id}

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data="pub"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
            ]
        ]
    )
    # Предпросмотр: если есть медиа — показываем его с подписью, иначе текст.
    await _send(context, msg.chat_id, uz, kind, file_id, reply_markup=kb, preview=True)


async def _media_url(context, file_id: str) -> str:
    """Публичный URL медиа на серверах Telegram (для link-preview).

    Виден только серверам Telegram как источник превью — читателям канала
    эта ссылка не показывается (link_preview_options.url отдельно от текста).
    """
    f = await context.bot.get_file(file_id)
    url = f.file_path or ""
    if not url.startswith("http"):
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{url}"
    return url


async def _send(context, chat_id, text, kind, file_id, reply_markup=None, preview=False):
    """Шлёт пост так, чтобы медиа и текст были ВМЕСТЕ, как в оригинале.

    • медиа + короткий текст (≤1024)  → одно медиа-сообщение с подписью;
    • медиа + длинный текст (>1024)   → link-preview: медиа показывается НАД
      полным текстом (до 4096) ОДНИМ сообщением. Это приём, которым каналы
      обходят лимит подписи в 1024 — фото/видео не как подпись, а как превью
      над текстом;
    • без медиа                        → обычное сообщение.
    HTML с безопасным фолбэком на обычный текст; если link-preview не прошёл —
    в крайнем случае медиа+текст раздельно (чтобы пост вообще ушёл).
    """
    text = text[:TEXT_LIMIT]
    senders = {
        "photo": context.bot.send_photo,
        "video": context.bot.send_video,
        "animation": context.bot.send_animation,
    }

    async def _as_caption(parse_mode):
        await senders[kind](chat_id=chat_id, **{kind: file_id}, caption=text,
                            parse_mode=parse_mode, reply_markup=reply_markup)

    async def _as_preview(parse_mode):
        url = await _media_url(context, file_id)
        lpo = LinkPreviewOptions(url=url, prefer_large_media=True,
                                 show_above_text=True, is_disabled=False)
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode,
                                       reply_markup=reply_markup, link_preview_options=lpo)

    async def _as_plain(parse_mode):
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode,
                                       reply_markup=reply_markup)

    if kind and file_id and len(text) <= CAPTION_LIMIT:
        primary = _as_caption
    elif kind and file_id:
        primary = _as_preview  # объединяем медиа+длинный текст одним сообщением
    else:
        primary = _as_plain

    try:
        await primary(ParseMode.HTML)
    except Exception as exc:  # noqa: BLE001 — кривой HTML → обычный текст
        log.warning("send HTML failed (%s), retry plain", type(exc).__name__)
        try:
            await primary(None)
        except Exception as exc2:  # noqa: BLE001 — крайний фолбэк, чтобы пост ушёл
            log.warning("primary failed (%s), fallback to split", type(exc2).__name__)
            if kind and file_id:
                await senders[kind](chat_id=chat_id, **{kind: file_id})
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q is None or q.from_user is None:
        return
    user_id = q.from_user.id
    if not _is_owner(user_id):
        await q.answer("Нет доступа")
        return
    await q.answer()

    if q.data == "cancel":
        _pending.pop(user_id, None)
        await q.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=q.message.chat_id, text="❌ Отменено — не опубликовано.")
        return

    item = _pending.pop(user_id, None)
    if not item:
        await q.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=q.message.chat_id,
                                       text="Черновик не найден — пришли пост заново.")
        return

    try:
        await _send(context, CHANNEL, item["text"], item["kind"], item["file_id"])
    except Exception as exc:  # noqa: BLE001
        log.exception("publish failed")
        await context.bot.send_message(chat_id=q.message.chat_id,
                                       text=f"❌ Ошибка публикации: {type(exc).__name__}")
        return

    await q.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(chat_id=q.message.chat_id, text="✅ Опубликовано в @buai_uz!")
    log.info("published to channel by owner=%s", user_id)


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Нет bot_token в Vault.")
    if not CHANNEL:
        raise SystemExit("Нет target_channel_id в Vault.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION | filters.PHOTO | filters.VIDEO | filters.ANIMATION)
            & ~filters.COMMAND,
            on_message,
        )
    )
    app.add_handler(CallbackQueryHandler(on_button))
    log.info("Умный бот запущен. @buaiuz_bot → канал %s. owner=%s", CHANNEL, OWNER_ID or "(TOFU)")
    app.run_polling()


if __name__ == "__main__":
    main()
