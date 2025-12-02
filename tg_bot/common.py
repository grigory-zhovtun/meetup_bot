from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    CallbackContext, CommandHandler, MessageHandler,
    Filters, CallbackQueryHandler
)
from tg_bot.talks import (
    start_ask_question, handle_question_if_waiting, show_schedule, 
    show_speaker_questions, subscribe_to_next_events, unsubscribe_from_events,
    notification_settings, handle_settings_callback, handle_subscribe_callback
)
from tg_bot.networking import (
    start_networking, handle_networking_message_if_active
)
from tg_bot.donations import start_donation, handle_donation_message_if_active
from datacenter.models import Speaker


def is_speaker(telegram_id: int) -> bool:
    try:
        return Speaker.objects.filter(telegram_id=telegram_id).exists()
    except Exception:
        return False


def get_main_menu_keyboard(telegram_id: int = None) -> ReplyKeyboardMarkup:
    if telegram_id and is_speaker(telegram_id):
        keyboard = [
            [KeyboardButton("Вопрос спикеру"), KeyboardButton("Программа")],
            [KeyboardButton("Нетворкинг"), KeyboardButton("Мои вопросы")],
            [KeyboardButton("Поддержать митап")],
        ]  
    else:
        keyboard = [
            [KeyboardButton("Вопрос спикеру"), KeyboardButton("Программа")],
            [KeyboardButton("Нетворкинг"), KeyboardButton("Поддержать митап")],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def start(update: Update, context: CallbackContext):
    user = update.effective_user
    keyboard = get_main_menu_keyboard(user.id)
    if is_speaker(user.id):
        text = (
            "Привет, {name}!\n\n"
            "Я бот PythonMeetup.\n\n"
            "Что могу для спикеров:\n"
            "• Показать вопросы к твоим выступлениям\n"
            "• Показать программу митапа\n"
            "• Помочь познакомиться с другими разработчиками\n"
            "• Присылать уведомления об изменениях\n\n"
            "Выбери, чем хочешь заняться сейчас:"
        ).format(name=user.first_name or "гость")
    else:
        text = (
            "Привет, {name}!\n\n"
            "Я бот PythonMeetup.\n\n"
            "Что умею:\n"
            "• Передать твой вопрос текущему спикеру\n"
            "• Показать программу митапа\n"
            "• Помочь познакомиться с другими разработчиками\n"
            "• Дать ссылку, чтобы поддержать мероприятие\n"
            "• Присылать уведомления об изменениях\n\n"
            "Выбери, чем хочешь заняться сейчас:"
        ).format(name=user.first_name or "гость")

    update.message.reply_text(text, reply_markup=keyboard)


def help_command(update: Update, context: CallbackContext):
    text = (
        "Команды:\n"
        "/start — описание и главное меню\n"
        "/help — помощь\n"
        "/update — обновить меню\n"
        "/subscribe — подписаться на уведомления\n"
        "/unsubscribe — отписаться от уведомлений\n"
        "/settings — настройки уведомлений\n"
        "/my_questions — для спикеров: посмотреть вопросы\n\n"
        "Основные действия доступны через кнопки внизу экрана."
    )
    update.message.reply_text(text)


def menu_router(update: Update, context: CallbackContext):
    text = update.message.text

    if handle_question_if_waiting(update, context):
        return

    if handle_networking_message_if_active(update, context):
        return

    if handle_donation_message_if_active(update, context):
        return

    if text == "Вопрос спикеру":
        start_ask_question(update, context)

    elif text == "Программа":
        show_schedule(update, context)

    elif text == "Нетворкинг":
        start_networking(update, context)

    elif text == "Поддержать митап":
        start_donation(update, context)

    elif text == "Мои вопросы":
        show_speaker_questions(update, context)

    else:
        update.message.reply_text(
            "Я тебя не очень понял\n"
            "Пожалуйста, воспользуйся кнопками внизу."
        )


def update_menu(update: Update, context: CallbackContext):
    start(update, context)

def register_common_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("update", update_menu))
    dispatcher.add_handler(CommandHandler("my_questions", show_speaker_questions))
    dispatcher.add_handler(CommandHandler("subscribe", subscribe_to_next_events))
    dispatcher.add_handler(CommandHandler("unsubscribe", unsubscribe_from_events))
    dispatcher.add_handler(CommandHandler("settings", notification_settings))
    dispatcher.add_handler(CommandHandler("program", show_schedule))

    dispatcher.add_handler(
        CallbackQueryHandler(
            handle_settings_callback, pattern='^(toggle_|info_)'
        )
    )
    
    dispatcher.add_handler(
        CallbackQueryHandler(
            handle_subscribe_callback, pattern='^subscribe_'
        )
    )
    
    dispatcher.add_handler(
        MessageHandler(Filters.text & ~Filters.command, menu_router)
    )
