import logging
import sys

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
except ModuleNotFoundError:
    sys.stderr.write("Модуль 'telegram' не найден. Установите его командой 'pip install python-telegram-bot' и попробуйте снова.\n")
    sys.exit(1)

# Настраиваем логирование с цветным выводом
class CustomFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[92m",
        "INFO": "\033[94m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[95m"
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.msg = f"{log_color}{record.msg}{self.RESET}"
        return super().format(record)

formatter = CustomFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Ваш Telegram API ключ
API_KEY = "8018543300:AAFgcrM7-n7d1kkiO35M96PHp-UCHtVagrU"

# Хранилище данных пользователей
user_data = {}
marketplace_data = []  # Глобальное хранилище для выставленных билетов

# Основная команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start и выводит приветственное сообщение."""
    keyboard = [
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton("💳 Продать билет", callback_data="sell_ticket")],
        [InlineKeyboardButton("📜 Полит. соглашение", callback_data="policy")],
        [InlineKeyboardButton("🏷️ Торговая площадка", callback_data="marketplace")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "Добро пожаловать! Я бот для безопасной перепродажи билетов на мероприятия.\n"
            "Используйте меню ниже для выбора нужного действия.",
            reply_markup=reply_markup
        )

# Обработчик кнопок меню
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки меню."""
    query = update.callback_query
    await query.answer()

    if query.data == "settings":
        keyboard = [
            [InlineKeyboardButton("💰 Реквизиты", callback_data="payment_details")],
            [InlineKeyboardButton("🌍 Выбор города", callback_data="select_city")],
            [InlineKeyboardButton("📞 Техническая поддержка", url="https://t.me/monekeny")],
            [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Пожалуйста, выберите одну из настроек:", reply_markup=reply_markup)

    elif query.data == "main_menu":
        await start(update, context)

    elif query.data == "marketplace":
        if marketplace_data:
            ticket_buttons = [
                [InlineKeyboardButton(f"{ticket['name']} - {ticket['price']} руб.", callback_data=f"market_details_{i}")]
                for i, ticket in enumerate(marketplace_data)
            ]
            ticket_buttons.append([InlineKeyboardButton("Назад", callback_data="main_menu")])

            reply_markup = InlineKeyboardMarkup(ticket_buttons)
            await query.edit_message_text("Список доступных билетов:", reply_markup=reply_markup)
        else:
            await query.edit_message_text("На торговой площадке пока нет билетов.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Назад", callback_data="main_menu")]
            ]))

    elif query.data.startswith("market_details_"):
        index = int(query.data.split("_")[2])
        ticket = marketplace_data[index]
        event_details = (
            f"Информация о билете:\nМероприятие: {ticket['name']}\n"
            f"Цена: {ticket['price']} руб.\n"
            "Вы хотите купить этот билет?"
        )
        keyboard = [
            [InlineKeyboardButton("Купить", callback_data=f"buy_ticket_{index}")],
            [InlineKeyboardButton("Назад", callback_data="marketplace")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(event_details, reply_markup=reply_markup)

    elif query.data.startswith("buy_ticket_"):
        index = int(query.data.split("_")[2])
        ticket = marketplace_data[index]
        marketplace_data.pop(index)
        await query.edit_message_text(
            f"Вы успешно купили билет \"{ticket['name']}\" за {ticket['price']} руб."
        )
        await start(update, context)

    elif query.data == "sell_ticket":
        await query.edit_message_text(
            "Продажа билета:\n"
            "1️⃣ Укажите название вашего билета (например, \"Концерт XYZ\").\n"
            "Пожалуйста, введите название билета:"
        )
        context.user_data["awaiting_ticket_name"] = True

# Обработка пользовательского ввода для билета и реквизитов
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения от пользователя."""
    user_id = update.message.from_user.id

    if context.user_data.get("awaiting_ticket_name"):
        ticket_name = update.message.text
        user_data.setdefault(user_id, {})["ticket_name"] = ticket_name
        context.user_data["awaiting_ticket_name"] = False
        context.user_data["awaiting_ticket_file"] = True
        await update.message.reply_text("Пожалуйста, отправьте файл или фото билета:")

    elif context.user_data.get("awaiting_ticket_file"):
        if update.message.document or update.message.photo:
            user_data[user_id]["ticket_file"] = (
                update.message.document or update.message.photo[-1].file_id
            )
            context.user_data["awaiting_ticket_file"] = False
            context.user_data["awaiting_ticket_price"] = True
            await update.message.reply_text("Введите цену билета в рублях:")
        else:
            await update.message.reply_text("Пожалуйста, отправьте файл или фото билета.")

    elif context.user_data.get("awaiting_ticket_price"):
        try:
            ticket_price = int(update.message.text)
            user_ticket = {
                "name": user_data[user_id]["ticket_name"],
                "price": ticket_price,
                "file_id": user_data[user_id].get("ticket_file")
            }
            marketplace_data.append(user_ticket)
            await update.message.reply_text(
                f"Ваш билет \"{user_ticket['name']}\" успешно выставлен на торговую площадку по цене {ticket_price} руб.!"
            )
            context.user_data["awaiting_ticket_price"] = False
            await start(update, context)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректное число для цены билета.")

    elif context.user_data.get("awaiting_sbp_phone"):
        phone = update.message.text
        user_data.setdefault(user_id, {})["payment_details"] = {"method": "СБП", "phone": phone}
        await update.message.reply_text("Ваши реквизиты сохранены! Возвращаю вас в меню настроек.")
        context.user_data["awaiting_sbp_phone"] = False
        await start(update, context)

    elif context.user_data.get("awaiting_card_number"):
        card_number = update.message.text
        user_data.setdefault(user_id, {})["payment_details"] = {"method": "Номер карты", "card": card_number}
        await update.message.reply_text("Ваши реквизиты сохранены! Возвращаю вас в меню настроек.")
        context.user_data["awaiting_card_number"] = False
        await start(update, context)

    elif context.user_data.get("awaiting_city"):
        city = update.message.text
        user_data.setdefault(user_id, {})["city"] = city
        await update.message.reply_text(f"Ваш город ({city}) сохранен! Возвращаю вас в меню настроек.")
        context.user_data["awaiting_city"] = False
        await start(update, context)

# Запуск бота
async def main():
    application = ApplicationBuilder().token(API_KEY).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(menu_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, text_handler))

    logger.info("Бот запущен и готов к работе.")
    await application.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    import asyncio

    nest_asyncio.apply()
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError as e:
        logger.error(f"Ошибка запуска: {e}")
