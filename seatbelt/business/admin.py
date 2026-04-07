from django.contrib import admin

from .models import (
    DailyDetectionStat,
    DetectObject,
    DetectResult,
    DetectTask,
    OperationLog,
    QueryLog,
    User,
    UserPlateBinding,
    ViolationRecord,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "phone", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "phone", "email")


@admin.register(DetectTask)
class DetectTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task_no",
        "task_type",
        "user",
        "status",
        "has_violation",
        "violation_count",
        "created_at",
    )
    list_filter = ("task_type", "status", "has_violation", "created_at")
    search_fields = ("task_no", "source_name", "notes")


@admin.register(DetectResult)
class DetectResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "result_index",
        "frame_index",
        "has_violation",
        "violation_count",
        "created_at",
    )
    list_filter = ("has_violation", "created_at")


@admin.register(DetectObject)
class DetectObjectAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "result",
        "object_type",
        "object_label",
        "confidence",
        "is_violation",
        "plate_text",
    )
    list_filter = ("object_type", "is_violation", "seatbelt_status", "created_at")
    search_fields = ("plate_text", "object_label", "source_model")


@admin.register(ViolationRecord)
class ViolationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "violation_no",
        "task",
        "plate_text",
        "status",
        "auditor",
        "created_at",
    )
    list_filter = ("status", "violation_type", "created_at")
    search_fields = ("violation_no", "plate_text", "audit_remark", "handled_remark")


@admin.register(UserPlateBinding)
class UserPlateBindingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plate_text", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "user__phone", "plate_text")


@admin.register(DailyDetectionStat)
class DailyDetectionStatAdmin(admin.ModelAdmin):
    list_display = ("id", "stat_date", "user", "detection_count", "created_at")
    list_filter = ("stat_date", "created_at")
    search_fields = ("user__username", "user__phone")


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "query_module", "result_count", "created_at")
    list_filter = ("query_module", "created_at")


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "operation_type", "target_type", "target_id", "created_at")
    list_filter = ("operation_type", "target_type", "created_at")
