from django.conf import settings

from ..business.models import DetectTask


def serialize_user(user):
    # 序列化用户
    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "wx_openid": user.wx_openid or "",
        "has_password": user.has_usable_password(),
        "is_password_set": user.has_usable_password(),
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def serialize_plate_binding(binding):
    # 序列化车牌绑定
    return {
        "id": binding.id,
        "user_id": binding.user_id,
        "plate_text": binding.plate_text,
        "is_active": binding.is_active,
        "created_at": binding.created_at.isoformat(),
        "updated_at": binding.updated_at.isoformat(),
    }


def task_result(task):
    # 计算任务结果
    if task.has_violation:
        return "not_wearing"
    if task.result_count > 0 and task.status == DetectTask.Status.COMPLETED:
        return "wearing"
    return "uncertain"


def serialize_object(obj, request=None):
    # 序列化目标
    image_url = ""
    if obj.crop_data:
        image_url = f"/api/objects/{obj.id}/image/"
        if request is not None:
            image_url = request.build_absolute_uri(image_url)

    return {
        "id": obj.id,
        "task_id": obj.task_id,
        "result_id": obj.result_id,
        "parent_object_id": obj.parent_object_id,
        "object_index": obj.object_index,
        "object_type": obj.object_type,
        "object_label": obj.object_label,
        "source_model": obj.source_model,
        "track_id": obj.track_id,
        "confidence": float(obj.confidence),
        "bbox": [obj.bbox_xmin, obj.bbox_ymin, obj.bbox_xmax, obj.bbox_ymax],
        "plate_text": obj.plate_text,
        "plate_score": float(obj.plate_score) if obj.plate_score is not None else None,
        "seatbelt_status": obj.seatbelt_status,
        "is_violation": obj.is_violation,
        "image_url": image_url,
        "extra_data": obj.extra_data,
        "created_at": obj.created_at.isoformat(),
        "updated_at": obj.updated_at.isoformat(),
    }


def serialize_violation(violation, request=None):
    # 序列化违规
    return {
        "result_image_url": (
            request.build_absolute_uri(f"{settings.MEDIA_URL}{violation.result.result_image}".replace("\\", "/"))
            if request is not None and getattr(getattr(violation, "result", None), "result_image", "")
            else (
                f"{settings.MEDIA_URL}{violation.result.result_image}".replace("\\", "/")
                if getattr(getattr(violation, "result", None), "result_image", "")
                else ""
            )
        ),
        "object_image_url": (
            request.build_absolute_uri(f"/api/objects/{violation.object_id}/image/")
            if request is not None and violation.object_id
            else (f"/api/objects/{violation.object_id}/image/" if violation.object_id else "")
        ),
        "id": violation.id,
        "violation_no": violation.violation_no,
        "task_id": violation.task_id,
        "task_no": violation.task.task_no if getattr(violation, "task", None) else "",
        "result_id": violation.result_id,
        "object_id": violation.object_id,
        "user_id": violation.user_id,
        "username": violation.user.username if getattr(violation, "user", None) else "",
        "violation_type": violation.violation_type,
        "status": int(violation.status),
        "plate_text": violation.plate_text,
        "auditor_id": violation.auditor_id,
        "auditor": violation.auditor.username if getattr(violation, "auditor", None) else "",
        "audit_time": violation.audit_time.isoformat() if violation.audit_time else None,
        "audit_remark": violation.audit_remark,
        "handled_time": violation.handled_time.isoformat() if violation.handled_time else None,
        "handled_remark": violation.handled_remark,
        "created_at": violation.created_at.isoformat(),
        "updated_at": violation.updated_at.isoformat(),
    }


def serialize_result(result, request=None, include_objects=True):
    # 序列化结果
    objects = []
    if include_objects:
        objects = [serialize_object(obj, request) for obj in result.detect_objects.all()]

    result_image_url = ""
    if result.result_image:
        result_image_url = f"{settings.MEDIA_URL}{result.result_image}".replace("\\", "/")
        if request is not None:
            result_image_url = request.build_absolute_uri(result_image_url)

    return {
        "id": result.id,
        "task_id": result.task_id,
        "result_index": result.result_index,
        "frame_index": result.frame_index,
        "frame_time_ms": result.frame_time_ms,
        "frame_file": result.frame_file,
        "result_image": result.result_image,
        "result_image_url": result_image_url,
        "image_width": result.image_width,
        "image_height": result.image_height,
        "object_count": result.object_count,
        "vehicle_count": result.vehicle_count,
        "person_count": result.person_count,
        "plate_count": result.plate_count,
        "violation_count": result.violation_count,
        "has_violation": result.has_violation,
        "max_confidence": float(result.max_confidence),
        "notes": result.notes,
        "metadata": result.metadata,
        "objects": objects,
        "violations": [serialize_violation(item, request) for item in result.violations.all()],
        "created_at": result.created_at.isoformat(),
        "updated_at": result.updated_at.isoformat(),
    }


def serialize_task(task, request=None, include_results=False):
    # 序列化任务
    file_url = task.source_file.url if task.source_file else ""
    if request is not None and file_url:
        file_url = request.build_absolute_uri(file_url)

    results = []
    if include_results:
        results = [serialize_result(result, request) for result in task.results.all()]

    return {
        "id": task.id,
        "task_no": task.task_no,
        "task_type": task.task_type,
        "source_name": task.source_name,
        "status": task.status,
        "progress": float(task.progress),
        "total_frames": task.total_frames,
        "processed_frames": task.processed_frames,
        "duration_ms": task.duration_ms,
        "result_count": task.result_count,
        "violation_count": task.violation_count,
        "has_violation": task.has_violation,
        "task_result": task_result(task),
        "notes": task.notes,
        "error_message": task.error_message,
        "file_url": file_url,
        "metadata": task.metadata,
        "user_id": task.user_id,
        "user": task.user.username if task.user else "",
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "results": results,
    }


def serialize_query_log(log):
    # 序列化查询日志
    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": log.user.username if getattr(log, "user", None) else "",
        "query_module": log.query_module,
        "query_params": log.query_params,
        "result_count": log.result_count,
        "user_agent": log.user_agent,
        "created_at": log.created_at.isoformat(),
        "updated_at": log.updated_at.isoformat(),
    }


def serialize_operation_log(log):
    # 序列化操作日志
    return {
        "id": log.id,
        "user_id": log.user_id,
        "username": log.user.username if getattr(log, "user", None) else "",
        "operation_type": log.operation_type,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "detail": log.detail,
        "request_method": log.request_method,
        "request_path": log.request_path,
        "user_agent": log.user_agent,
        "created_at": log.created_at.isoformat(),
        "updated_at": log.updated_at.isoformat(),
    }
