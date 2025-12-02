from telegram import Update
from telegram.ext import CallbackContext
from django.utils import timezone

from datacenter.models import Participant, Donation


DONATION_STATE_KEY = "donation_state"
DONATION_AMOUNT_KEY = "donation_amount"


def start_donation(update: Update, context: CallbackContext) -> None:
    context.user_data[DONATION_STATE_KEY] = "waiting_for_amount"

    text = (
        "Спасибо, что хочешь поддержать митап!\n\n"
        "Донаты помогают оплачивать площадку и делать следующие мероприятия лучше.\n\n"
        "Если хочешь задонатить, напиши сумму в рублях цифрами (например: 300 или 500).\n"
        "Если передумал, просто напиши «В другой раз»."
    )

    update.message.reply_text(text)


def handle_donation_message_if_active(update: Update, context: CallbackContext) -> bool:
    state = context.user_data.get(DONATION_STATE_KEY)
    if state != "waiting_for_amount":
        return False

    text_raw = update.message.text or ""
    text = text_raw.strip().lower()

    if text in ("в другой раз", "не сейчас", "нет", "потом", "отмена"):
        context.user_data[DONATION_STATE_KEY] = None
        context.user_data.pop(DONATION_AMOUNT_KEY, None)

        update.message.reply_text(
            "Без проблем!\n"
            "Спасибо, что вообще задумался поддержать митап.\n"
            "Можешь в любой момент вернуться к донату через кнопку «Поддержать митап»."
        )
        return True

    digits = "".join(char for char in text_raw if char.isdigit())
    if not digits:
        update.message.reply_text(
            "Я не понял сумму\n"
            "Пожалуйста, напиши только число в рублях, например: 200 или 500.\n"
            "Или напиши «В другой раз», если передумал."
        )
        return True

    amount = int(digits)
    if amount <= 0:
        update.message.reply_text(
            "Сумма должна быть больше нуля\n"
            "Напиши, пожалуйста, сумму в рублях или «В другой раз»."
        )
        return True

    context.user_data[DONATION_AMOUNT_KEY] = amount
    context.user_data[DONATION_STATE_KEY] = None

    user = update.effective_user

    try:
        participant, created = Participant.objects.get_or_create(
            telegram_id=user.id,
            defaults={
                "username": user.username,
                "full_name": f"{user.first_name} {user.last_name or ''}".strip()
            }
        )
        
        # Сохраняем донат в базу данных
        donation = Donation.objects.create(
            participant=participant,
            amount=amount
        )
        
        print(f"[DONATION] Saved to DB: ID={donation.id}, from {user.id} (@{user.username}): {amount} RUB")

        update.message.reply_text(
            f"Спасибо! Ты выбрал(а) поддержать митап на {amount} ₽\n\n"
            "Ссылка для оплаты: https://example.com/donation\n\n"
            f"Твой донат записан. Дата: {timezone.localtime(donation.created_at).strftime('%d.%m.%Y %H:%M')}"
        )
    except Exception as e:
        print(f"Error saving donation: {e}")
        update.message.reply_text(
            "Произошла ошибка при обработке доната. Попробуйте позже"
        )
    
    return True
