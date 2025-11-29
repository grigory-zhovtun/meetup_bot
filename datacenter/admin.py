from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from .models import (
    Event,
    Speaker,
    Speech,
    Participant,
    Question,
    Subscription,
    Donation,
    Notification
)
from tg_bot.notifications import get_notification_service


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'created_at', 'subscribers_count')
    list_filter = ('is_active', 'date', 'created_at')
    search_fields = ('title', 'description')
    date_hierarchy = 'date'
    ordering = ('-date',)
    actions = ['send_program_change_notification', 'send_new_event_notification', 'send_reminder_notification']

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'date')
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
    )

    def subscribers_count(self, obj):
        return obj.subscription_set.count()
    subscribers_count.short_description = 'Подписчики'

    def send_program_change_notification(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Пожалуйста, выберите только одно мероприятие.", level='error')
            return

        event = queryset.first()
    
        return HttpResponseRedirect(
            f"/admin/datacenter/event/{event.id}/program-change/"
        )

    def program_change_view(self, request, object_id):
        from .models import Event
        from .notifications import get_notification_service
    
        event = Event.objects.get(id=object_id)
    
        if request.method == 'POST':
            change_description = request.POST.get('change_description', '')
            if change_description:
                notification_service = get_notification_service()
                sent_count = notification_service.send_program_change_notification(event, change_description)
                messages.success(request, f"Уведомление отправлено {sent_count} подписчикам")
                return HttpResponseRedirect("/admin/datacenter/event/")
            else:
                messages.error(request, "Пожалуйста, введите описание изменений")
    
        context = {
            'title': f'Уведомление об изменении программы: {event.title}',
            'event': event,
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
        }
        return render(request, 'admin/program_change_notification.html', context)

    def send_new_event_notification(self, request, queryset):
        sent_count = 0
        for event in queryset:
            count = notification_service.send_new_event_notification(event)
            sent_count += count
            self.message_user(request, f"Уведомления о мероприятии '{event.title}' отправлены {count} пользователям")
    send_new_event_notification.short_description = "Отправить уведомление о новом мероприятии"

    def send_reminder_notification(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Пожалуйста, выберите только одно мероприятие.", level='error')
            return

        event = queryset.first()
        count = notification_service.send_reminder_notification(event)
        self.message_user(request, f"Напоминания о мероприятии '{event.title}' отправлены {count} пользователям")
    send_reminder_notification.short_description = "Отправить напоминание о мероприятии"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/program-change/',
                self.admin_site.admin_view(self.program_change_view),
                name='event-program-change',
            ),
        ]
        return custom_urls + urls

    def program_change_view(self, request, object_id):
        from .models import Event
        event = Event.objects.get(id=object_id)
        
        if request.method == 'POST':
            change_description = request.POST.get('change_description', '')
            if change_description:
                sent_count = notification_service.send_program_change_notification(event, change_description)
                messages.success(request, f"Уведомление отправлено {sent_count} подписчикам")
                return HttpResponseRedirect("/admin/datacenter/event/")
            else:
                messages.error(request, "Пожалуйста, введите описание изменений")

        context = {
            'title': f'Уведомление об изменении программы: {event.title}',
            'event': event,
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
        }
        return render(request, 'admin/program_change_notification.html', context)


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

    def speeches_count(self, obj):
        return obj.speech_set.count()
    speeches_count.short_description = 'Кол-во выступлений'


@admin.register(Speech)
class SpeechAdmin(admin.ModelAdmin):
    list_display = ('title', 'speaker', 'event', 'start_time', 'is_active')
    list_filter = ('is_active', 'event', 'speaker')
    search_fields = ('title', 'description')
    date_hierarchy = 'start_time'
    ordering = ('-start_time',)
    actions = ['send_speech_reminder']

    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'speaker', 'event')
        }),
        ('Время проведения', {
            'fields': ('start_time', 'end_time')
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
    )

    def send_speech_reminder(self, request, queryset):
        sent_count = 0
        for speech in queryset:
            count = notification_service.send_reminder_notification(speech.event, speech)
            sent_count += count
            self.message_user(request, f"Напоминания о выступлении '{speech.title}' отправлены {count} пользователям")
    send_speech_reminder.short_description = "Отправить напоминание о выступлении"


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('get_display_name', 'telegram_id', 'company', 'position', 'questions_count', 'registered_at')
    search_fields = ('full_name', 'username', 'company')
    list_filter = ('experience', 'registered_at')
    date_hierarchy = 'registered_at'
    actions = ['export_telegram_ids']

    fieldsets = (
        ('Основная информация', {
            'fields': ('full_name', 'username', 'telegram_id')
        }),
        ('Профессиональная информация', {
            'fields': ('company', 'position', 'experience')
        }),
    )

    def get_display_name(self, obj):
        return obj.full_name or f"@{obj.username}" or str(obj.telegram_id)
    get_display_name.short_description = 'Имя участника'

    def export_telegram_ids(self, request, queryset):
        telegram_ids = [str(participant.telegram_id) for participant in queryset]
        response = HttpResponse("\n".join(telegram_ids), content_type="text/plain")
        response['Content-Disposition'] = 'attachment; filename="telegram_ids.txt"'
        return response
    export_telegram_ids.short_description = "Экспорт Telegram ID"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('get_short_text', 'participant', 'speech', 'created_at', 'is_answered')
    list_filter = ('is_answered', 'speech', 'created_at')
    search_fields = ('question_text', 'participant__full_name')
    date_hierarchy = 'created_at'
    list_editable = ('is_answered',)

    fieldsets = (
        ('Вопрос', {
            'fields': ('question_text', 'speech', 'participant')
        }),
        ('Статус', {
            'fields': ('is_answered',)
        }),
    )

    def get_short_text(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    get_short_text.short_description = 'Текст вопроса'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('participant', 'event', 'notify_program_changes', 'notify_new_events', 'notify_reminders', 'subscribed_at')
    list_filter = ('event', 'subscribed_at', 'notify_program_changes', 'notify_new_events', 'notify_reminders')
    search_fields = ('participantfull_name', 'participantusername', 'event__title')
    date_hierarchy = 'subscribed_at'
    readonly_fields = ('subscribed_at',)
    list_editable = ('notify_program_changes', 'notify_new_events', 'notify_reminders')


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('participant', 'amount', 'created_at')
    list_filter = ('created_at',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'event', 'notification_type', 'is_sent', 'created_at')
    list_filter = ('notification_type', 'is_sent', 'created_at', 'event')
    search_fields = ('title', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        return False
