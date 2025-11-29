import logging
from django.conf import settings
from telegram import Bot

from datacenter.models import Subscription, Notification, UserNotification, Participant
from tg_bot.config import TELEGRAM_BOT_TOKEN


logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot):
        self.bot = bot
    
    def send_program_change_notification(self, event, change_description):
        try:
            subscriptions = Subscription.objects.filter(
                event=event,
                notify_program_changes=True
            ).select_related('participant')
            
            if not subscriptions.exists():
                logger.info(f"No subscribers for program changes in event {event.title}")
                return 0
            
            notification = Notification.objects.create(
                event=event,
                title=f"Изменения в программе {event.title}",
                message=change_description,
                notification_type='program_change'
            )
            
            sent_count = 0
            for subscription in subscriptions:
                try:
                    message_text = (
                        f"*Изменения в программе*\n\n"
                        f"*{event.title}*\n\n"
                        f"{change_description}\n\n"
                        f"Используй /program чтобы посмотреть актуальное расписание"
                    )
                    
                    self.bot.send_message(
                        chat_id=subscription.participant.telegram_id,
                        text=message_text,
                        parse_mode='Markdown'
                    )
                    
                    UserNotification.objects.create(
                        participant=subscription.participant,
                        notification=notification
                    )
                    sent_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to send notification to {subscription.participant.telegram_id}: {e}")
            
            notification.is_sent = True
            notification.save()
            
            logger.info(f"Sent {sent_count} program change notifications for event {event.title}")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error sending program change notifications: {e}")
            return 0

    
    def send_new_event_notification(self, event):
        try:
            participants = Participant.objects.filter(
                subscription__notify_new_events=True
            ).distinct()
            
            notification = Notification.objects.create(
                event=event,
                title=f"Новое мероприятие: {event.title}",
                message=event.description,
                notification_type='new_event'
            )
            
            sent_count = 0
            for participant in participants:
                try:
                    self.bot.send_message(
                        chat_id=participant.telegram_id,
                        text=f"*Новое мероприятие!*\n\n*{event.title}*\n\n{event.description}\n\n"
                             f"Дата: {event.date.strftime('%d.%m.%Y %H:%M')}\n"
                             f"Используй /subscribe чтобы подписаться на уведомления"
                    )
                    UserNotification.objects.create(
                        participant=participant,
                        notification=notification
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send new event notification to {participant.telegram_id}: {e}")
            
            notification.is_sent = True
            notification.save()
            
            logger.info(f"Sent {sent_count} new event notifications")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error sending new event notifications: {e}")
            return 0
    
    def send_reminder_notification(self, event, speech=None):
        try:
            subscriptions = Subscription.objects.filter(
                event=event,
                notify_reminders=True
            ).select_related('participant')
            
            if speech:
                message = f"*Скоро начнется выступление!*\n\n{speech.speaker.name}\n*{speech.title}*\n\nНачало: {speech.start_time.strftime('%H:%M')}"
                title = f"Напоминание: {speech.title}"
            else:
                message = f"*Скоро начнется мероприятие!*\n\n{event.title}\n\nНачало: {event.date.strftime('%H:%M')}"
                title = f"Напоминание: {event.title}"
            
            notification = Notification.objects.create(
                event=event,
                title=title,
                message=message,
                notification_type='reminder'
            )
            
            sent_count = 0
            for subscription in subscriptions:
                try:
                    self.bot.send_message(
                        chat_id=subscription.participant.telegram_id,
                        text=message
                    )
                    UserNotification.objects.create(
                        participant=subscription.participant,
                        notification=notification
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send reminder to {subscription.participant.telegram_id}: {e}")
            
            notification.is_sent = True
            notification.save()
            
            logger.info(f"Sent {sent_count} reminder notifications")
            return sent_count
            
        except Exception as e:
            logger.error(f"Error sending reminder notifications: {e}")
            return 0

def get_notification_service():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    return NotificationService(bot)
