from django.utils import timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler

from datacenter.models import Event, Speech, Speaker, Participant, Question, Subscription
from .notifications import get_notification_service


def start_ask_question(update: Update, context: CallbackContext) -> None:
    active_speech = get_active_speech()
    if not active_speech:
        update.message.reply_text(
            "В данный момент нет активных выступлений.\n"
            "Вопросы можно задавать только во время выступления спикера."
        )
        return

    speaker_name = active_speech.speaker.name
    context.user_data["awaiting_question"] = True
    context.user_data["active_speech_id"] = active_speech.id

    update.message.reply_text(
        f"Окей! Напиши, пожалуйста, свой вопрос для текущего спикера: {speaker_name}.\n"
        f"Тема: {active_speech.title}\n\n"
        "Если передумаешь, нажми любую кнопку внизу, и я отменю ввод вопроса."
    )


def handle_question_if_waiting(
        update: Update,
        context: CallbackContext
    ) -> bool:
    if not context.user_data.get("awaiting_question"):
        return False

    question_text = update.message.text
    user = update.effective_user
    speech_id = context.user_data.get("active_speech_id")

    if not speech_id:
        update.message.reply_text("Ошибка: не найдено активное выступление")
        context.user_data["awaiting_question"] = False
        return True

    try:
        participant, created = Participant.objects.get_or_create(
            telegram_id=user.id,
            defaults={
                "username": user.username,
                "full_name": f"{user.first_name} {user.last_name or ''}".strip()
            }
        )
        speech = Speech.objects.get(id=speech_id)
        question = Question.objects.create(
            speech=speech,
            participant=participant,
            question_text=question_text
        )

        print(f"[QUESTION] from {user.id} (@{user.username}): {question_text}")

        context.user_data["awaiting_question"] = False
        context.user_data.pop("active_speech_id", None)

        update.message.reply_text(
            "Спасибо! Я передал твой вопрос спикеру.\n"
            "Можешь задать ещё один или вернуться к программе/нетворкингу через меню."
        )
    
    except Speech.DoesNotExist:
        update.message.reply_text("Ошибка: выступление не найдено")
        context.user_data["awaiting_question"] = False
    except Exception as e:
        print(f"Error saving question: {e}")
        update.message.reply_text(
            "Произошла ошибка при сохранении вопроса. Попробуйте позже"
        )
    return True


def _format_time(dt):
    if not dt:
        return "Не указано"
    local_dt = timezone.localtime(dt)
    return local_dt.strftime("%H:%M")


def _format_datetime(dt):
    if not dt:
        return "Не указано"
    local_dt = timezone.localtime(dt)
    return local_dt.strftime("%d.%m.%Y %H:%M")


def show_schedule(update: Update, context: CallbackContext) -> None:
    try:
        # Получаем все активные мероприятия
        active_events = Event.objects.filter(is_active=True).order_by('date')
        if not active_events.exists():
            update.message.reply_text("В данный момент нет активных событий")
            return

        # Получаем все выступления из всех активных мероприятий
        speeches = Speech.objects.filter(
            event__in=active_events
        ).select_related("speaker", "event").order_by("start_time")

        if not speeches.exists():
            update.message.reply_text(
                "Программа выступлений пока не доступна"
            )
            return

        # Группируем выступления по мероприятиям
        schedule_text = ""
        current_event = None
        
        for speech in speeches:
            # Если это новое мероприятие, добавляем заголовок
            if current_event != speech.event:
                current_event = speech.event
                if schedule_text:
                    schedule_text += "\n"
                schedule_text += f"Программа: {current_event.title}\n\n"

            now = timezone.now()
            if speech.start_time <= now <= speech.end_time:
                status = "Сейчас"
            elif now < speech.start_time:
                status = "Будет"
            else:
                status = "Завершено"
            
            # Форматируем время: если начало и конец в один день, показываем дату только для начала
            start_local = timezone.localtime(speech.start_time)
            end_local = timezone.localtime(speech.end_time)
            
            if start_local.date() == end_local.date():
                # Оба времени в один день - показываем дату только для начала
                time_range = f"{_format_datetime(speech.start_time)}-{end_local.strftime('%H:%M')}"
            else:
                # Разные дни - показываем дату для обоих
                time_range = f"{_format_datetime(speech.start_time)}-{_format_datetime(speech.end_time)}"
            
            schedule_text += f"{status}, {time_range}\n"
            schedule_text += f"спикер - {speech.speaker.name}\n"
            schedule_text += f"тема: {speech.title}\n\n"

        update.message.reply_text(schedule_text)

    except Exception as e:
        print(f"Error showing schedule: {e}")
        update.message.reply_text("Произошла ошибка при загрузке программы")


def get_active_speech():
    try:
        now = timezone.now()
        return Speech.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            # is_active=True   ## нет необходимости, определяется автоматом
        ).select_related("speaker").first()
    except Exception as e:
        print(f"Error getting active speech: {e}")
        return None


def show_speaker_questions(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    telegram_id = user.id

    speaker = Speaker.objects.filter(telegram_id=telegram_id).first()
    if not speaker:
        update.message.reply_text(
            "Эта команда доступна только спикерам.\n"
            "Если ты докладчик, но не видишь свои вопросы, "
            "скажи организатору, чтобы он привязал твой Telegram к профилю спикера."
        )
        return

    event = Event.objects.filter(is_active=True).first()

    speech = None

    active_speech = get_active_speech()
    if active_speech and active_speech.speaker_id == speaker.id:
        speech = active_speech

    if not speech and event:
        speech = (
            Speech.objects.filter(event=event, speaker=speaker)
            .order_by("-start_time")
            .first()
        )

    if not speech:
        update.message.reply_text(
            "Я не нашёл твоих докладов в текущем мероприятии.\n"
            "Проверь, что в админке ты привязан как спикер к нужному выступлению."
        )
        return

    questions = (
        Question.objects.filter(speech=speech)
        .select_related("participant")
        .order_by("created_at")
    )

    if not questions.exists():
        update.message.reply_text(
            f"К докладу «{speech.title}» пока нет вопросов.\n"
            "Можешь открыть бот ещё раз позже, они появятся к концу выступления."
        )
        return

    header = (
        f"Вопросы к твоему докладу:\n"
        f"«{speech.title}»\n\n"
    )

    lines = []
    for index, question in enumerate(questions, start=1):
        participant = question.participant
        username = participant.username or "ник не указан"
        name = participant.full_name or username

        contact = f"@{username}" if participant.username else "контакт: ник не указан"

        lines.append(
            f"{index}. От {name} ({contact}):\n"
            f"   {question.question_text}\n"
        )

    text = header + "\n".join(lines)

    update.message.reply_text(text)


def subscribe_to_next_events(update: Update, context: CallbackContext) -> None:
    user = update.effective_user

    active_events = Event.objects.filter(is_active=True).order_by('date')

    if not active_events.exists():
        update.message.reply_text(
            "Сейчас нет ни одного мероприятия в базе, "
            "но организаторы смогут добавить тебя позже"
        )
        return

    # Если только одно мероприятие, подписываем сразу
    if active_events.count() == 1:
        event = active_events.first()
        _subscribe_to_event(update, context, event.id)
        return

    # Если несколько мероприятий, показываем выбор
    keyboard = []
    for event in active_events:
        event_date = timezone.localtime(event.date).strftime('%d.%m.%Y %H:%M')
        button_text = f"{event.title} ({event_date})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"subscribe_{event.id}")])
    
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="subscribe_cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "Выбери мероприятие, на которое хочешь подписаться:\n\n"
        "Ты будешь получать уведомления о:\n"
        "• Изменениях в программе\n"
        "• Напоминаниях о начале\n"
    )
    
    update.message.reply_text(text, reply_markup=reply_markup)


def _subscribe_to_event(update: Update, context: CallbackContext, event_id: int) -> None:
    """Внутренняя функция для подписки на конкретное мероприятие"""
    try:
        event = Event.objects.get(id=event_id, is_active=True)
    except Event.DoesNotExist:
        if update.callback_query:
            update.callback_query.answer("Мероприятие не найдено или неактивно")
        else:
            update.message.reply_text("Мероприятие не найдено или неактивно")
        return

    user = update.effective_user if update.message else update.callback_query.from_user
    
    participant, _ = Participant.objects.get_or_create(
        telegram_id=user.id,
        defaults={
            "username": user.username,
            "full_name": f"{user.first_name} {user.last_name or ''}".strip(),
        },
    )

    subscription, created = Subscription.objects.get_or_create(
        participant=participant,
        event=event,
        defaults={
            'notify_program_changes': True,
            'notify_new_events': True,
            'notify_reminders': True
        }
    )

    if created:
        text = (
            f"Готово! Ты подписан на уведомления о мероприятии:\n"
            f"*{event.title}*\n\n"
            f"Ты будешь получать уведомления о:\n"
            f"• Изменениях в программе\n"
            f"• Напоминаниях о начале\n\n"
            f"Используй /settings чтобы настроить уведомления"
        )
    else:
        text = (
            f"Ты уже подписан на уведомления о мероприятии:\n"
            f"*{event.title}*\n\n"
            f"Используй /settings чтобы изменить настройки"
        )

    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text, parse_mode='Markdown')
    else:
        update.message.reply_text(text, parse_mode='Markdown')


def handle_subscribe_callback(update: Update, context: CallbackContext) -> None:
    """Обработчик callback для выбора мероприятия при подписке"""
    query = update.callback_query
    data = query.data

    if data == "subscribe_cancel":
        query.answer()
        query.edit_message_text("Подписка отменена")
        return

    if data.startswith("subscribe_"):
        event_id = int(data.replace("subscribe_", ""))
        _subscribe_to_event(update, context, event_id)


def unsubscribe_from_events(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    try:
        participant = Participant.objects.get(telegram_id=user.id)
        subscriptions = Subscription.objects.filter(participant=participant)
        
        if not subscriptions.exists():
            update.message.reply_text("Ты не подписан на уведомления.")
            return
        
        subscriptions.update(
            notify_program_changes=False,
            notify_new_events=False,
            notify_reminders=False
        )
        
        update.message.reply_text(
            "Ты отписался от всех уведомлений.\n"
            "Используй /subscribe чтобы снова подписаться"
        )
        
    except Participant.DoesNotExist:
        update.message.reply_text("Сначала зарегистрируйся через /start")
    except Exception as e:
        logger.error(f"Error unsubscribing: {e}")
        update.message.reply_text("Произошла ошибка. Попробуй позже.")


def notification_settings(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    
    try:
        participant = Participant.objects.get(telegram_id=user.id)
        event = Event.objects.filter(is_active=True).first()
        
        if not event:
            update.message.reply_text("Сейчас нет активных мероприятий.")
            return
        
        subscription, created = Subscription.objects.get_or_create(
            participant=participant,
            event=event,
            defaults={
                'notify_program_changes': True,
                'notify_new_events': True,
                'notify_reminders': True
            }
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "ВКЛ" if subscription.notify_program_changes else "ВЫКЛ",
                    callback_data=f"toggle_program_{subscription.id}"
                ),
                InlineKeyboardButton("Изменения программы", callback_data="info_program")
            ],
            [
                InlineKeyboardButton(
                    "ВКЛ" if subscription.notify_new_events else "ВЫКЛ", 
                    callback_data=f"toggle_events_{subscription.id}"
                ),
                InlineKeyboardButton("Новые мероприятия", callback_data="info_events")
            ],
            [
                InlineKeyboardButton(
                    "ВКЛ" if subscription.notify_reminders else "ВЫКЛ",
                    callback_data=f"toggle_reminders_{subscription.id}"
                ),
                InlineKeyboardButton("Напоминания", callback_data="info_reminders")
            ],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status_text = (
            f"*Настройки уведомлений для {event.title}*\n\n"
            f"Изменения программы: {'ВКЛ' if subscription.notify_program_changes else 'ВЫКЛ'}\n"
            f"Новые мероприятия: {'ВКЛ' if subscription.notify_new_events else 'ВЫКЛ'}\n"
            f"Напоминания: {'ВКЛ' if subscription.notify_reminders else 'ВЫКЛ'}\n\n"
            "Нажми на кнопку ВКЛ/ВЫКЛ чтобы изменить настройку"
        )
        
        update.message.reply_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Participant.DoesNotExist:
        update.message.reply_text("Сначала зарегистрируйся через /start")
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        update.message.reply_text("Произошла ошибка. Попробуй позже.")


def handle_settings_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    
    data = query.data
    
    if data.startswith('toggle_program_'):
        subscription_id = data.replace('toggle_program_', '')
        _toggle_setting(query, subscription_id, 'notify_program_changes')
        
    elif data.startswith('toggle_events_'):
        subscription_id = data.replace('toggle_events_', '')
        _toggle_setting(query, subscription_id, 'notify_new_events')
        
    elif data.startswith('toggle_reminders_'):
        subscription_id = data.replace('toggle_reminders_', '')
        _toggle_setting(query, subscription_id, 'notify_reminders')
        
    elif data.startswith('info_'):
        info_text = {
            'info_program': 'Получать уведомления об изменениях в программе мероприятия',
            'info_events': 'Получать уведомления о новых мероприятиях',
            'info_reminders': 'Получать напоминания о начале выступлений'
        }
        query.answer(info_text.get(data, "Информация"), show_alert=True)


def _toggle_setting(query, subscription_id, setting_name):
    try:
        subscription = Subscription.objects.get(id=subscription_id)
        current_value = getattr(subscription, setting_name)
        setattr(subscription, setting_name, not current_value)
        subscription.save()
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "ВКЛ" if subscription.notify_program_changes else "ВЫКЛ",
                    callback_data=f"toggle_program_{subscription.id}"
                ),
                InlineKeyboardButton("Изменения программы", callback_data="info_program")
            ],
            [
                InlineKeyboardButton(
                    "ВКЛ" if subscription.notify_new_events else "ВЫКЛ", 
                    callback_data=f"toggle_events_{subscription.id}"
                ),
                InlineKeyboardButton("Новые мероприятия", callback_data="info_events")
            ],
            [
                InlineKeyboardButton(
                    "ВКЛ" if subscription.notify_reminders else "ВЫКЛ",
                    callback_data=f"toggle_reminders_{subscription.id}"
                ),
                InlineKeyboardButton("Напоминания", callback_data="info_reminders")
            ],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status_text = (
            f"*Настройки уведомлений*\n\n"
            f"Изменения программы: {'ВКЛ' if subscription.notify_program_changes else 'ВЫКЛ'}\n"
            f"Новые мероприятия: {'ВКЛ' if subscription.notify_new_events else 'ВЫКЛ'}\n"
            f"Напоминания: {'ВКЛ' if subscription.notify_reminders else 'ВЫКЛ'}\n\n"
            "Нажми на кнопку ВКЛ/ВЫКЛ чтобы изменить настройку"
        )
        
        query.edit_message_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Subscription.DoesNotExist:
        query.edit_message_text("Ошибка: подписка не найдена")
    except Exception as e:
        logger.error(f"Error toggling setting: {e}")
        query.edit_message_text("Произошла ошибка. Попробуй позже.")
