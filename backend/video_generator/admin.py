from django.contrib import admin
from .models import Character, CreditAccount, CreditTransaction, Subscription, UsageEvent, VideoProject, VideoScene

@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display=("title","user","version_number","status","duration","aspect_ratio","generation_attempt","created_at","updated_at")
    list_filter=("status","input_type","aspect_ratio","duration","provider")
    search_fields=("title","prompt","user__username","user__email")
    readonly_fields=("created_at","updated_at","generation_attempt","processing_started_at","completed_at","failed_at")
@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display=("name","project","reference_image_url","reference_generation_attempt","created_at")
    search_fields=("name","project__title","project__user__username")
    readonly_fields=("created_at","reference_generation_attempt")
@admin.register(VideoScene)
class VideoSceneAdmin(admin.ModelAdmin):
    list_display=("project","scene_number","status","duration","provider","generation_attempt","created_at")
    list_filter=("status","provider","duration")
    search_fields=("project__title","prompt")
    readonly_fields=("created_at","generation_attempt","processing_started_at","completed_at","failed_at")
@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display=("user","balance","monthly_allowance","updated_at")
    search_fields=("user__username","user__email")
    readonly_fields=("updated_at",)
@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display=("account","kind","amount","project","idempotency_key","created_at")
    list_filter=("kind",)
    search_fields=("account__user__username","account__user__email","idempotency_key","note")
    readonly_fields=("created_at","idempotency_key")
@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    list_display=("user","kind","quantity","credits","project","scene","created_at")
    list_filter=("kind",)
    search_fields=("user__username","user__email","idempotency_key")
    readonly_fields=("created_at","idempotency_key")
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display=("user","plan_code","status","provider","current_period_end","cancel_at_period_end","updated_at")
    list_filter=("plan_code","status","provider","cancel_at_period_end")
    search_fields=("user__username","user__email","provider_customer_id","provider_subscription_id")
    readonly_fields=("created_at","updated_at")
