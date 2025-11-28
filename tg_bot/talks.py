from django.utils import timezone
from telegram import Update
from telegram.ext import CallbackContext

from datacenter.models import Event, Speech, Speaker, Participant, Question, Subscription


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


def show_schedule(update: Update, context: CallbackContext) -> None:
    try:
        event = Event.objects.filter(is_active=True).first()
        if not event:
            update.message.reply_text("В данный момент нет активных событий")
            return

        speeches = Speech.objects.filter(event=event).select_related("speaker").order_by("start_time")

        if not speeches:
            update.message.reply_text(
                "Программа выступлений пока не доступна"
            )
            return

        schedule_text = f"Программа: {event.title}\n\n"

        for speech in speeches:
            now = timezone.now()
            if speech.start_time <= now <= speech.end_time:
                status = "Сейчас"
            elif now < speech.start_time:
                status = "Будет"
            else:
                status = "Завершено"
            schedule_text += f"{status}, {speech.start_time.strftime('%H:%M')}-{speech.end_time.strftime('%H:%M')}\n"
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

    event = Event.objects.filter(is_active=True).first()
    if not event:
        event = Event.objects.order_by("-date").first()

    if not event:
        update.message.reply_text(
            "Сейчас нет ни одного мероприятия в базе, "
            "но организаторы смогут добавить тебя позже"
        )
        return

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
    )

    if created:
        update.message.reply_text(
            "Готово! Мы напомним тебе о следующих митапах."
        )
    else:
        update.message.reply_text(
            "Ты уже подписан на уведомления о следующем митапе."
        )