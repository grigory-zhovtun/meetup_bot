from telegram import Update
from telegram.ext import CallbackContext
from datacenter.models import Participant

PROFILE_QUESTIONS = [
    (
        "role",
        "Расскажи в двух словах, кто ты и чем занимаешься (например: Python backend, data scientist, DevOps)?",
    ),
    (
        "experience",
        "Сколько у тебя опыта в IT? (например: 6 месяцев, 2 года, 10+ лет)",
    ),
    (
        "looking_for",
        "С кем хочешь познакомиться на митапе? (джуны, сеньоры, тимлиды, работодатели, единомышленники и т.п.)",
    ),
]

# ВРЕМЕННО вместо Django API.
# Это нужно будет заменить на запрос к бэкенду.
DUMMY_CANDIDATES = [
    {
        "full_name": "Аня",
        "username": "anya_dev",
        "role": "Python backend",
        "experience": "2 года",
        "looking_for": "других backend-разработчиков и тимлидов",
    },
    {
        "full_name": "Илья",
        "username": "ilya_data",
        "role": "Data engineer",
        "experience": "3 года",
        "looking_for": "data-людей и ML-разработчиков",
    },
]


def start_networking(update: Update, context: CallbackContext) -> None:
    has_profile = context.user_data.get("networking_has_profile", False)

    if not has_profile:
        text = (
            "Классно, что хочешь познакомиться с другими разработчиками!\n\n"
            "Как это работает:\n"
            "• Ты заполняешь короткую анкету о себе\n"
            "• Я буду подбирать тебе других участников митапа\n"
            "• Я покажу их анкету и контакт в Telegram\n"
            "• Если не понравится, то можно будет пропустить и попросить следующего\n\n"
            "Давай начнём с анкеты"
        )
        update.message.reply_text(text)
        start_profile_form(update, context)
    else:
        text = (
            "Снова нетворкинг? Отлично!\n"
            "У тебя уже есть анкета, я попробую подобрать тебе новых людей.\n"
        )
        update.message.reply_text(text)
        start_matching(update, context)


def start_profile_form(update: Update, context: CallbackContext) -> None:
    context.user_data["networking_state"] = "filling_profile"
    context.user_data["networking_step"] = 0
    context.user_data["networking_form"] = {}

    _ask_current_profile_question(update, context)


def _ask_current_profile_question(update: Update, context: CallbackContext) -> None:
    step = context.user_data.get("networking_step", 0)

    if step >= len(PROFILE_QUESTIONS):
        _finish_profile(update, context)
        return

    _, question_text = PROFILE_QUESTIONS[step]
    update.message.reply_text(question_text)


def handle_networking_message_if_active(update: Update, context: CallbackContext) -> bool:
    state = context.user_data.get("networking_state")

    if state == "filling_profile":
        return _handle_profile_answer(update, context)

    if state == "browsing_candidates":
        return _handle_candidate_flow(update, context)

    return False


def _handle_profile_answer(update: Update, context: CallbackContext) -> bool:
    text = update.message.text
    step = context.user_data.get("networking_step", 0)
    form = context.user_data.get("networking_form", {})

    if step < len(PROFILE_QUESTIONS):
        key, _ = PROFILE_QUESTIONS[step]
        form[key] = text.strip()
        context.user_data["networking_form"] = form
        context.user_data["networking_step"] = step + 1

    if context.user_data["networking_step"] < len(PROFILE_QUESTIONS):
        _ask_current_profile_question(update, context)
    else:
        _finish_profile(update, context)

    return True


def _finish_profile(update: Update, context: CallbackContext) -> None:
    form = context.user_data.get("networking_form", {})
    user = update.effective_user

    # TODO: здесь должен быть вызов Django API, что-то вроде:
    participant, _ = Participant.objects.get_or_create(
        telegram_id=user.id,
        defaults={'username': user.username}
    )
    participant.position = form.get('role', '')
    participant.experience = form.get('experience', '')
    participant.looking_for = form.get('looking_for', '')
    if not participant.full_name:
        participant.full_name = user.full_name

    participant.save()
    # print(f"[NETWORKING PROFILE] from {user.id} (@{user.username}): {form}")

    context.user_data["networking_state"] = None
    context.user_data["networking_step"] = 0
    context.user_data["networking_has_profile"] = True

    update.message.reply_text(
        "Готово! Я сохранил твою анкету для нетворкинга.\n\n"
        "Дальше я буду подбирать тебе других участников митапа."
    )

    start_matching(update, context)


def start_matching(update: Update, context: CallbackContext) -> None:
    context.user_data["networking_state"] = "browsing_candidates"

    candidate = _fetch_next_candidate_stub(update.effective_user.id, context)

    if not candidate:
        context.user_data["networking_state"] = None
        update.message.reply_text(
            "Ты один из первых, кто заполнил анкету\n"
            "Пока других анкет нет, но как только люди начнут заполнять, "
            "я смогу кого-то тебе предложить.\n\n"
            "Чуть позже просто снова нажми «Нетворкинг», чтобы попробовать ещё раз."
        )
        # TODO: Тут можно подписать пользователя
        # на уведомление из Django, когда появятся новые анкеты
        return

    context.user_data["networking_current_candidate"] = candidate
    _show_candidate(update, context, candidate)


def _handle_candidate_flow(update: Update, context: CallbackContext) -> bool:
    text = (update.message.text or "").strip().lower()

    if text.startswith("след"):
        _show_next_candidate(update, context)
        return True

    if text.startswith("стоп") or text in ("хватит", "stop"):
        context.user_data["networking_state"] = None
        context.user_data.pop("networking_current_candidate", None)

        update.message.reply_text(
            "Окей, остановимся на этом\n"
            "Если захочешь продолжить знакомиться, снова нажми «Нетворкинг»."
        )
        return True

    update.message.reply_text(
        "Если не хочешь общаться с текущим человеком, напиши «Следующий».\n"
        "Если пока хватит, напиши «Стоп».\n"
        "А написать ему можно просто перейдя по нику в сообщении выше"
    )
    return True


def _show_candidate(update: Update, context: CallbackContext, candidate: dict) -> None:
    username = candidate.get("username")
    full_name = candidate.get("full_name") or "Не указано"
    role = candidate.get("role") or "Не указано"
    experience = candidate.get("experience") or "Не указано"
    looking_for = candidate.get("looking_for") or "Не указано"

    text = (
        "Нашёл тебе человека для знакомства:\n\n"
        f"Имя: {full_name}\n"
        f"Кто: {role}\n"
        f"Опыт: {experience}\n"
        f"Ищет: {looking_for}\n\n"
    )

    if username:
        text += f"Связаться: @{username}\n\n"
    else:
        text += "Связаться: ник в Telegram не указан\n\n"

    text += (
        "Если не хочешь общаться с этим человеком, напиши «Следующий».\n"
        "Если пока хватит, напиши «Стоп»."
    )

    update.message.reply_text(text)


def _show_next_candidate(update: Update, context: CallbackContext) -> None:
    candidate = _fetch_next_candidate_stub(update.effective_user.id, context)

    if not candidate:
        context.user_data["networking_state"] = None
        context.user_data.pop("networking_current_candidate", None)

        update.message.reply_text(
            "Похоже, больше анкет пока нет ️\n"
            "Можешь вернуться позже — нажми «Нетворкинг», когда захочешь продолжить."
        )
        return

    context.user_data["networking_current_candidate"] = candidate
    _show_candidate(update, context, candidate)


def _fetch_next_candidate_stub(user_telegram_id: int, context: CallbackContext):
    """
    Временная заглушка.
    Возвращает следующего кандидата из DUMMY_CANDIDATES, которого пользователь ещё не видел.
    Эта функция должна дергать Django API.
    """
    seen_ids = context.user_data.get("networking_seen_dummy_ids")
    if seen_ids is None:
        seen_ids = set()
    if not isinstance(seen_ids, set):
        seen_ids = set()

    for idx, candidate in enumerate(DUMMY_CANDIDATES):
        if idx in seen_ids:
            continue
        seen_ids.add(idx)
        context.user_data["networking_seen_dummy_ids"] = seen_ids
        return candidate

    return None