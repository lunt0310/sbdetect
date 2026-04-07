from django.contrib.auth.models import AbstractUser
from django.db import models


class BaseTimeModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser, BaseTimeModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "管理员"
        AUDITOR = "auditor", "审核员"
        USER = "user", "普通用户"

    phone = models.CharField(max_length=20, blank=True, default="")
    wx_openid = models.CharField(max_length=64, null=True, blank=True, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)

    class Meta:
        db_table = "user"
        db_table_comment = "用户表"
        verbose_name = "用户"
        verbose_name_plural = "用户"
        indexes = [
            models.Index(fields=["role"], name="idx_user_role"),
            models.Index(fields=["created_at"], name="idx_user_created_at"),
        ]


class UserPlateBinding(BaseTimeModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="plate_bindings")
    plate_text = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "ser_plate_binding"
        db_table_comment = "用户车牌绑定表"
        verbose_name = "用户车牌绑定"
        verbose_name_plural = "用户车牌绑定"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "plate_text"], name="uk_user_plate_binding_user_plate"),
        ]
        indexes = [
            models.Index(fields=["user", "is_active", "created_at"], name="idx_plate_binding_user_active"),
            models.Index(fields=["plate_text", "is_active"], name="idx_plate_binding_plate_active"),
        ]


class DailyDetectionStat(BaseTimeModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="daily_detection_stats")
    stat_date = models.DateField()
    detection_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "daily_detection_stat"
        db_table_comment = "每日检测统计表"
        verbose_name = "每日检测统计"
        verbose_name_plural = "每日检测统计"
        ordering = ["-stat_date", "user_id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "stat_date"], name="uk_daily_detection_stat_user_date"),
        ]
        indexes = [
            models.Index(fields=["stat_date"], name="idx_daily_stat_date"),
            models.Index(fields=["user", "stat_date"], name="idx_daily_stat_user_date"),
        ]


class DetectTask(BaseTimeModel):
    class TaskType(models.TextChoices):
        IMAGE = "image", "图片"
        VIDEO = "video", "视频"

    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        RUNNING = "running", "处理中"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失败"
        CANCELLED = "cancelled", "已取消"

    task_no = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detect_tasks",
    )
    task_type = models.CharField(max_length=10, choices=TaskType.choices)
    source_name = models.CharField(max_length=255)
    source_file = models.FileField(upload_to="seatbelt/%Y/%m/%d/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_frames = models.PositiveIntegerField(default=1)
    processed_frames = models.PositiveIntegerField(default=0)
    duration_ms = models.BigIntegerField(null=True, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    violation_count = models.PositiveIntegerField(default=0)
    has_violation = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True, default="")
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "detect_task"
        db_table_comment = "检测任务表"
        verbose_name = "检测任务"
        verbose_name_plural = "检测任务"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "created_at"], name="idx_task_user_status_ct"),
            models.Index(fields=["task_type", "status", "created_at"], name="idx_task_type_status_ct"),
            models.Index(fields=["has_violation", "created_at"], name="idx_task_violation_ct"),
        ]


class DetectResult(BaseTimeModel):
    task = models.ForeignKey(DetectTask, on_delete=models.CASCADE, related_name="results")
    result_index = models.PositiveIntegerField(default=1)
    frame_index = models.PositiveIntegerField(null=True, blank=True)
    frame_time_ms = models.BigIntegerField(null=True, blank=True)
    frame_file = models.CharField(max_length=255, blank=True, default="")
    result_image = models.CharField(max_length=255, blank=True, default="")
    image_width = models.PositiveIntegerField(default=0)
    image_height = models.PositiveIntegerField(default=0)
    object_count = models.PositiveIntegerField(default=0)
    vehicle_count = models.PositiveIntegerField(default=0)
    person_count = models.PositiveIntegerField(default=0)
    plate_count = models.PositiveIntegerField(default=0)
    violation_count = models.PositiveIntegerField(default=0)
    has_violation = models.BooleanField(default=False)
    max_confidence = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "detect_result"
        db_table_comment = "检测结果表"
        verbose_name = "检测结果"
        verbose_name_plural = "检测结果"
        ordering = ["result_index", "id"]
        constraints = [
            models.UniqueConstraint(fields=["task", "result_index"], name="uk_task_result_index"),
        ]
        indexes = [
            models.Index(fields=["task", "frame_index"], name="idx_result_task_frame"),
            models.Index(fields=["has_violation", "created_at"], name="idx_result_violation_ct"),
        ]


class DetectObject(BaseTimeModel):
    class ObjectType(models.TextChoices):
        VEHICLE = "vehicle", "车辆"
        PERSON = "person", "人物"
        SEATBELT = "seatbelt", "安全带"
        LICENSE_PLATE = "license_plate", "车牌"

    task = models.ForeignKey(DetectTask, on_delete=models.CASCADE, related_name="detect_objects")
    result = models.ForeignKey(DetectResult, on_delete=models.CASCADE, related_name="detect_objects")
    parent_object = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    object_index = models.PositiveIntegerField(default=1)
    track_id = models.CharField(max_length=64, blank=True, default="")
    object_type = models.CharField(max_length=20, choices=ObjectType.choices)
    object_label = models.CharField(max_length=50)
    source_model = models.CharField(max_length=50, blank=True, default="")
    confidence = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    bbox_xmin = models.IntegerField()
    bbox_ymin = models.IntegerField()
    bbox_xmax = models.IntegerField()
    bbox_ymax = models.IntegerField()
    crop_data = models.BinaryField(null=True, blank=True)
    crop_content_type = models.CharField(max_length=100, default="image/jpeg")
    plate_text = models.CharField(max_length=32, blank=True, default="")
    plate_score = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    seatbelt_status = models.CharField(max_length=20, blank=True, default="")
    is_violation = models.BooleanField(default=False)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "detect_object"
        db_table_comment = "检测目标明细表"
        verbose_name = "检测目标"
        verbose_name_plural = "检测目标"
        ordering = ["object_index", "id"]
        indexes = [
            models.Index(fields=["result", "object_type"], name="idx_object_result_type"),
            models.Index(fields=["result", "is_violation"], name="idx_object_result_vio"),
            models.Index(fields=["parent_object"], name="idx_object_parent"),
            models.Index(fields=["track_id"], name="idx_object_track"),
            models.Index(fields=["plate_text"], name="idx_object_plate_text"),
        ]


class ViolationRecord(BaseTimeModel):
    class ViolationType(models.TextChoices):
        NO_SEATBELT = "no_seatbelt", "未系安全带"

    class Status(models.IntegerChoices):
        PROCESSED = 0, "检测完成"
        PENDING_REVIEW = 1, "申请待审核"
        CONFIRMED = 2, "申请审核通过"
        REJECTED = 3, "申请审核驳回"

    violation_no = models.CharField(max_length=32, unique=True)
    task = models.ForeignKey(DetectTask, on_delete=models.CASCADE, related_name="violations")
    result = models.ForeignKey(DetectResult, on_delete=models.CASCADE, related_name="violations")
    object = models.ForeignKey(DetectObject, on_delete=models.CASCADE, related_name="violations")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_violations",
    )
    violation_type = models.CharField(
        max_length=30,
        choices=ViolationType.choices,
        default=ViolationType.NO_SEATBELT,
    )
    plate_text = models.CharField(max_length=32, blank=True, default="")
    status = models.PositiveSmallIntegerField(choices=Status.choices, default=Status.PROCESSED)
    auditor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audited_violations",
    )
    audit_time = models.DateTimeField(null=True, blank=True)
    audit_remark = models.CharField(max_length=500, blank=True, default="")
    handled_time = models.DateTimeField(null=True, blank=True)
    handled_remark = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "violation_record"
        db_table_comment = "违规记录表"
        verbose_name = "违规记录"
        verbose_name_plural = "违规记录"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_violation_status_ct"),
            models.Index(fields=["user", "status", "created_at"], name="idx_violation_user_status_ct"),
            models.Index(fields=["plate_text", "status"], name="idx_violation_plate_status"),
            models.Index(fields=["auditor", "audit_time"], name="idx_violation_auditor_time"),
        ]


class QueryLog(BaseTimeModel):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="query_logs",
    )
    query_module = models.CharField(max_length=50)
    query_params = models.JSONField(default=dict, blank=True)
    result_count = models.IntegerField(default=0)
    user_agent = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "query_log"
        db_table_comment = "查询日志表"
        verbose_name = "查询日志"
        verbose_name_plural = "查询日志"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_query_user_ct"),
            models.Index(fields=["query_module", "created_at"], name="idx_query_module_ct"),
        ]


class OperationLog(BaseTimeModel):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_logs",
    )
    operation_type = models.CharField(max_length=50)
    target_type = models.CharField(max_length=50, blank=True, default="")
    target_id = models.BigIntegerField(null=True, blank=True)
    detail = models.TextField(blank=True, default="")
    request_method = models.CharField(max_length=10, blank=True, default="")
    request_path = models.CharField(max_length=255, blank=True, default="")
    user_agent = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "operation_log"
        db_table_comment = "操作日志表"
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"], name="idx_operation_user_ct"),
            models.Index(fields=["target_type", "target_id"], name="idx_operation_target"),
            models.Index(fields=["operation_type", "created_at"], name="idx_operation_type_ct"),
        ]
