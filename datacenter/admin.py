from django.contrib import admin
from .models import (
    Event,
    Speaker,
    Speech,
    Participant,
    Question,
    Subscription
)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'is_active', 'created_at')
    list_filter = ('is_active', 'date', 'created_at')
    search_fields = ('title', 'description')
    date_hierarchy = 'date'
    ordering = ('-date',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'date')
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
    )


@admin.register(Speaker)
class SpeakerAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_id', 'speeches_count')
    search_fields = ('name',)
    list_editable = ('telegram_id',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('name',)
        }),
        ('Telegram', {
            'fields': ('telegram_id',)
        }),
    )


@admin.register(Speech)
class SpeechAdmin(admin.ModelAdmin):
    list_display = [
       'title',
       'speaker',
       'event',
       'start_time',
       'end_time',
       'is_active'
    ]
    list_filter = ['event', 'is_active']


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'company', 'position', 'registered_at']
    serch_fields = ['full_name', 'company']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['participant', 'speech', 'created_at', 'is_answered']
    list_filter = ['speech', 'is_answered']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['participant', 'event', 'subscribed_at']
