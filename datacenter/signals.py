from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import Speech

@receiver(pre_delete, sender=Speech)
def speech_pre_delete(sender, instance, **kwargs):
    from tg_bot.notifications import get_notification_service
    notification_service = get_notification_service()
    change_description = f"Выступление '{instance.title}' было удалено из программы."
    notification_service.send_program_change_notification(instance.event, change_description)
