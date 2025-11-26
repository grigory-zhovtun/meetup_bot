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
        return self.title


class Participant(models.Model):
    telegram_id = models.BigIntegerField(unique=True, blank=True)
    username = models.CharField(max_length=255, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    company = models.CharField(max_length=255, blank=True)
    position = models.CharField(max_length=255, blank=True)
    experience = models.CharField(max_length=100, blank=True)
    registered_at = models.DateTimeField(blank=True)

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

    class Meta:
        ordering = ('participant',)
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def __str__(self):
        return f"{self.participant.full_name or self.participant.telegram_id} → {self.event.title}"