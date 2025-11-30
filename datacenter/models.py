from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Event(models.Model):
    title = models.CharField('Название', max_length=255)
    description = models.TextField('Описание')
    date = models.DateTimeField('Дата')
    is_active = models.BooleanField('Активно', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    @property
    def total_speeches(self):
        return self.speech_set.count()

    @property
    def total_participants(self):
        return self.subscription_set.count()

    class Meta:
        ordering = ('title',)
        verbose_name = 'Конференция'
        verbose_name_plural = 'Конференции'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            old_event = Event.objects.get(pk=self.pk)
            important_fields_changed = (
                old_event.title != self.title or
                old_event.date != self.date or
                old_event.description != self.description
            )
            
            super().save(*args, **kwargs)
            
            if important_fields_changed:
                from tg_bot.notifications import get_notification_service
                notification_service = get_notification_service()
                change_description = f"Изменения в мероприятии '{self.title}'. Проверьте актуальную информацию."
                notification_service.send_program_change_notification(self, change_description)
        else:
            super().save(*args, **kwargs)


class Speaker(models.Model):
    name = models.CharField('Имя', max_length=255)
    telegram_id = models.BigIntegerField(null=True, blank=True)

    @property
    def speeches_count(self):
        return self.speech_set.count()

    class Meta:
        ordering = ('name',)
        verbose_name = 'Спикер'
        verbose_name_plural = 'Спикеры'

    def __str__(self):
        return self.name


class Speech(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    speaker = models.ForeignKey(Speaker, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ('event',)
        verbose_name = 'Презентация'
        verbose_name_plural = 'Презентации'

    def __str__(self):
        return f'{self.title} - {self.speaker.name}'

    def save(self, *args, **kwargs):
        if self.pk:
            old_speech = Speech.objects.get(pk=self.pk)
            important_fields_changed = (
                old_speech.title != self.title or
                old_speech.start_time != self.start_time or
                old_speech.end_time != self.end_time or
                old_speech.speaker_id != self.speaker_id
            )
            
            super().save(*args, **kwargs)
            
            if important_fields_changed:
                from tg_bot.notifications import get_notification_service
                notification_service = get_notification_service()
                change_description = f"Изменения в выступлении '{self.title}'. Проверьте актуальное расписание."
                notification_service.send_program_change_notification(self.event, change_description)
        else:
            super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        event = self.event
        title = self.title
        super().delete(*args, **kwargs)
        
        from .notifications import get_notification_service
        notification_service = get_notification_service()
        change_description = f"Выступление '{title}' было удалено из программы."
        notification_service.send_program_change_notification(event, change_description)


class Participant(models.Model):
    telegram_id = models.BigIntegerField(unique=True, blank=True)
    username = models.CharField(max_length=255, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    company = models.CharField(max_length=255, blank=True)
    position = models.CharField(max_length=255, blank=True)
    experience = models.CharField(max_length=100, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    looking_for = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Кого ищет",
        help_text="Например: 'Ищу Python-разработчика' или 'Ищу инвестора'"
    )

    @property
    def questions_count(self):
        return self.question_set.count()

    class Meta:
        ordering = ('registered_at',)
        verbose_name = 'Участник'
        verbose_name_plural = 'Участники'

    def __str__(self):
        if self.full_name:
            return self.full_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"Participant {self.telegram_id}"


class Question(models.Model):
    speech = models.ForeignKey(Speech, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    question_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_answered = models.BooleanField(default=False)

    class Meta:
        ordering = ('speech',)
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'

    def __str__(self):
        return f"Question to {self.speech.title}: {self.question_text[:50]}..."


class Subscription(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    notify_program_changes = models.BooleanField(default=True)
    notify_new_events = models.BooleanField(default=True)
    notify_reminders = models.BooleanField(default=True)

    class Meta:
        unique_together = ['participant', 'event']
        ordering = ('participant',)
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def __str__(self):
        return f"{self.participant.full_name or self.participant.telegram_id} → {self.event.title}"


class Donation(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, verbose_name="Кто задонатил")
    amount = models.IntegerField(verbose_name="Сумма (руб)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата и время")

    class Meta:
        verbose_name = "Донат"
        verbose_name_plural = "Донаты"

    def __str__(self):
        return f"{self.amount}₽ от {self.participant}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('program_change', 'Изменение программы'),
        ('new_event', 'Новое мероприятие'),
        ('reminder', 'Напоминание'),
        ('general', 'Общее уведомление'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='general')
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'


class UserNotification(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Уведомлние для {self.participant} - {self.notification.title}"
        