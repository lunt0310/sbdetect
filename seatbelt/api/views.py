import json
import logging
import re
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.contrib.auth import authenticate
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..business.models import (
    DailyDetectionStat,
    DetectObject,
    DetectTask,
    OperationLog,
    QueryLog,
    User,
    UserPlateBinding,
    ViolationRecord,
)
from ..detection.pipeline import SeatbeltDetectionService
from ..inference import ModelRuntimeError
from .jwt_utils import (
    ACCESS_TOKEN_EXPIRES_IN,
    JwtAuthError,
    build_token_payload,
    create_access_token,
    decode_token,
    get_request_user,
)
from .logging import write_operation_log, write_query_log
from .serializers import (
    serialize_operation_log,
    serialize_plate_binding,
    serialize_query_log,
    serialize_task,
    serialize_user,
    serialize_violation,
)

logger = logging.getLogger("seatbelt.views")


def json_success(data=None, message="success", status=200):
    # 返回成功结果
    payload = {"code": 0, "message": message}
    if data is not None:
        payload["data"] = data
    return JsonResponse(payload, status=status)


def json_error(message, code=400, status=400):
    # 返回错误结果
    return JsonResponse({"code": code, "message": message}, status=status)


def get_request_data(request):
    # 获取请求数据
    content_type = request.content_type or ""
    if "application/json" in content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return {}
    return request.POST


def parse_int(value, default):
    # 解析整数
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value):
    # 解析布尔值
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    return None


def build_task_no():
    # 生成任务号
    return f"T{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


def normalize_plate_text(value):
    # 规范车牌文本
    text = str(value or "").strip().upper()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9A-Z\u4e00-\u9fff]", "", text)
    return text


def is_valid_phone(phone):
    # 校验手机号
    return bool(re.fullmatch(r"1\d{10}", str(phone or "").strip()))


def build_client_username(phone):
    # 为小程序用户生成用户名
    phone = str(phone or "").strip()
    base_username = f"u_{phone}"
    username = base_username
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{suffix}"
        suffix += 1
    return username


def build_wechat_username(openid):
    suffix = str(openid or "").strip()[-10:] or uuid.uuid4().hex[:10]
    base_username = f"wx_{suffix}"
    username = base_username
    suffix_index = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{suffix_index}"
        suffix_index += 1
    return username


def require_wechat_miniapp_settings():
    app_id = getattr(settings, "WECHAT_MINIAPP_APP_ID", "").strip()
    app_secret = getattr(settings, "WECHAT_MINIAPP_APP_SECRET", "").strip()

    return app_id, app_secret


def call_wechat_json_api(url, *, method="GET", payload=None):
    request_body = None
    request_headers = {}
    if payload is not None:
        request_body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url, data=request_body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="ignore")
        logger.warning("WeChat API http error status=%s body=%s", exc.code, response_body)
        raise ValueError("微信接口请求失败") from exc
    except URLError as exc:
        logger.warning("WeChat API network error error=%s", exc)
        raise ValueError("微信接口网络异常") from exc

    try:
        data = json.loads(response_body or "{}")
    except json.JSONDecodeError as exc:
        logger.warning("WeChat API invalid json body=%s", response_body)
        raise ValueError("微信接口返回异常") from exc

    if data.get("errcode") not in {None, 0}:
        logger.warning("WeChat API business error response=%s", data)
        raise ValueError(data.get("errmsg") or "微信接口调用失败")
    return data


def wechat_code_to_session(code):
    app_id, app_secret = require_wechat_miniapp_settings()
    query = urlencode(
        {
            "appid": app_id,
            "secret": app_secret,
            "js_code": str(code or "").strip(),
            "grant_type": "authorization_code",
        }
    )
    return call_wechat_json_api(f"https://api.weixin.qq.com/sns/jscode2session?{query}")


def wechat_get_access_token():
    app_id, app_secret = require_wechat_miniapp_settings()
    query = urlencode(
        {
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        }
    )
    response = call_wechat_json_api(f"https://api.weixin.qq.com/cgi-bin/token?{query}")
    access_token = str(response.get("access_token", "")).strip()
    if not access_token:
        raise ValueError("寰俊access_token鑾峰彇澶辫触")
    return access_token


def wechat_code_to_phone_info(phone_code):
    access_token = wechat_get_access_token()
    response = call_wechat_json_api(
        f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}",
        method="POST",
        payload={"code": str(phone_code or "").strip()},
    )
    phone_info = response.get("phone_info") or {}
    phone = str(phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber") or "").strip()
    if not phone:
        raise ValueError("寰俊鎵嬫満鍙疯幏鍙栧け璐?")
    return {
        "phone": phone,
        "country_code": str(phone_info.get("countryCode", "")).strip(),
    }


def merge_wechat_user_into_existing_user(source_user, target_user, *, phone, password):
    if not source_user.wx_openid:
        raise ValueError("当前微信账号缺少openid")
    source_openid = source_user.wx_openid
    if target_user.wx_openid and target_user.wx_openid != source_openid:
        raise ValueError("该手机号已绑定其他微信账号")

    with transaction.atomic():
        if source_user.pk != target_user.pk:
            source_user.wx_openid = None
            source_user.save(update_fields=["wx_openid"])

        target_user.wx_openid = source_openid
        target_user.phone = phone
        update_fields = ["wx_openid", "phone"]
        if not target_user.has_usable_password():
            target_user.set_password(password)
            update_fields.append("password")
        target_user.save(update_fields=update_fields)

        for binding in UserPlateBinding.objects.filter(user=source_user):
            existing_binding = UserPlateBinding.objects.filter(
                user=target_user,
                plate_text=binding.plate_text,
            ).first()
            if existing_binding:
                if binding.is_active and not existing_binding.is_active:
                    existing_binding.is_active = True
                    existing_binding.save(update_fields=["is_active", "updated_at"])
                binding.delete()
            else:
                binding.user = target_user
                binding.save(update_fields=["user"])

        for stat in DailyDetectionStat.objects.filter(user=source_user):
            existing_stat = DailyDetectionStat.objects.filter(
                user=target_user,
                stat_date=stat.stat_date,
            ).first()
            if existing_stat:
                existing_stat.detection_count += stat.detection_count
                existing_stat.save(update_fields=["detection_count", "updated_at"])
                stat.delete()
            else:
                stat.user = target_user
                stat.save(update_fields=["user"])

        DetectTask.objects.filter(user=source_user).update(user=target_user)
        ViolationRecord.objects.filter(user=source_user).update(user=target_user)
        QueryLog.objects.filter(user=source_user).update(user=target_user)
        OperationLog.objects.filter(user=source_user).update(user=target_user)

        if source_user.pk != target_user.pk:
            source_user.delete()

    return target_user


def get_user_active_plate_bindings(user):
    # 获取用户当前有效绑定车牌
    return UserPlateBinding.objects.filter(user=user, is_active=True).order_by("-created_at")


def serialize_user_with_plate_bindings(user):
    # 返回用户和车牌绑定
    bindings = [serialize_plate_binding(item) for item in get_user_active_plate_bindings(user)]
    return {
        **serialize_user(user),
        "bound_plates": bindings,
    }


def get_auth_user_or_response(request):
    # 获取认证用户
    try:
        user = get_request_user(request)
    except JwtAuthError as exc:
        return None, json_error(str(exc), 401, 401)
    if user is None:
        return None, json_error("请先登录", 401, 401)
    return user, None


def is_staff_user(user):
    # 判断管理角色
    return user.role in {User.Role.ADMIN, User.Role.AUDITOR}


def require_staff_user(request):
    # 校验管理权限
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return None, error_response
    if not is_staff_user(user):
        return None, json_error("无权限访问", 403, 403)
    return user, None


def require_admin_user(request):
    # 校验管理员权限
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return None, error_response
    if user.role != User.Role.ADMIN:
        return None, json_error("仅管理员可操作", 403, 403)
    return user, None


def apply_date_filters(queryset, date_from, date_to, field_name="created_at"):
    # 追加日期筛选
    if date_from:
        queryset = queryset.filter(**{f"{field_name}__date__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field_name}__date__lte": date_to})
    return queryset


def increment_daily_detection_stat(user, *, stat_date=None):
    if user is None:
        return

    stat_date = stat_date or timezone.localdate()
    with transaction.atomic():
        stat, _ = DailyDetectionStat.objects.get_or_create(
            user=user,
            stat_date=stat_date,
            defaults={"detection_count": 0},
        )
        DailyDetectionStat.objects.filter(pk=stat.pk).update(
            detection_count=F("detection_count") + 1,
            updated_at=timezone.now(),
        )


def build_today_detection_stats(user):
    today = timezone.localdate()
    today_user_total = (
        DailyDetectionStat.objects.filter(user=user, stat_date=today)
        .values_list("detection_count", flat=True)
        .first()
        or 0
    )
    user_task_total = DetectTask.objects.filter(user=user).count()
    data = {
        "today_date": today.isoformat(),
        "today_user_detection_total": today_user_total,
        "today_detection_total": today_user_total,
        "user_task_total": user_task_total,
    }

    if is_staff_user(user):
        today_system_total = DailyDetectionStat.objects.filter(stat_date=today).aggregate(total=Sum("detection_count"))[
            "total"
        ] or 0
        system_task_total = DetectTask.objects.count()
        data["today_system_detection_total"] = today_system_total
        data["today_detection_total"] = today_system_total
        data["system_task_total"] = system_task_total

    return data


def normalize_review_action(value):
    text = str(value or "").strip().lower()
    action_map = {
        "0": ViolationRecord.Status.PROCESSED,
        "1": ViolationRecord.Status.PENDING_REVIEW,
        "2": ViolationRecord.Status.CONFIRMED,
        "3": ViolationRecord.Status.REJECTED,
        str(ViolationRecord.Status.PROCESSED): ViolationRecord.Status.PROCESSED,
        str(ViolationRecord.Status.PENDING_REVIEW): ViolationRecord.Status.PENDING_REVIEW,
        str(ViolationRecord.Status.CONFIRMED): ViolationRecord.Status.CONFIRMED,
        str(ViolationRecord.Status.REJECTED): ViolationRecord.Status.REJECTED,
        "confirm": ViolationRecord.Status.CONFIRMED,
        "confirmed": ViolationRecord.Status.CONFIRMED,
        ViolationRecord.Status.CONFIRMED: ViolationRecord.Status.CONFIRMED,
        "reject": ViolationRecord.Status.REJECTED,
        "rejected": ViolationRecord.Status.REJECTED,
        ViolationRecord.Status.REJECTED: ViolationRecord.Status.REJECTED,
        "complete": ViolationRecord.Status.PROCESSED,
        "completed": ViolationRecord.Status.PROCESSED,
        "process": ViolationRecord.Status.PROCESSED,
        "processed": ViolationRecord.Status.PROCESSED,
        ViolationRecord.Status.PROCESSED: ViolationRecord.Status.PROCESSED,
        "pending": ViolationRecord.Status.PENDING_REVIEW,
        "pending_review": ViolationRecord.Status.PENDING_REVIEW,
        ViolationRecord.Status.PENDING_REVIEW: ViolationRecord.Status.PENDING_REVIEW,
    }
    return action_map.get(text)


def normalize_violation_query_status(value):
    text = str(value or "").strip().lower()
    status_map = {
        "0": ViolationRecord.Status.PROCESSED,
        "1": ViolationRecord.Status.PENDING_REVIEW,
        "2": ViolationRecord.Status.CONFIRMED,
        "3": ViolationRecord.Status.REJECTED,
        str(ViolationRecord.Status.PROCESSED): ViolationRecord.Status.PROCESSED,
        str(ViolationRecord.Status.PENDING_REVIEW): ViolationRecord.Status.PENDING_REVIEW,
        str(ViolationRecord.Status.CONFIRMED): ViolationRecord.Status.CONFIRMED,
        str(ViolationRecord.Status.REJECTED): ViolationRecord.Status.REJECTED,
        "pending": ViolationRecord.Status.PENDING_REVIEW,
        "pending_review": ViolationRecord.Status.PENDING_REVIEW,
        ViolationRecord.Status.PENDING_REVIEW: ViolationRecord.Status.PENDING_REVIEW,
        "confirm": ViolationRecord.Status.CONFIRMED,
        "confirmed": ViolationRecord.Status.CONFIRMED,
        ViolationRecord.Status.CONFIRMED: ViolationRecord.Status.CONFIRMED,
        "reject": ViolationRecord.Status.REJECTED,
        "rejected": ViolationRecord.Status.REJECTED,
        ViolationRecord.Status.REJECTED: ViolationRecord.Status.REJECTED,
        "complete": ViolationRecord.Status.PROCESSED,
        "completed": ViolationRecord.Status.PROCESSED,
        "process": ViolationRecord.Status.PROCESSED,
        "processed": ViolationRecord.Status.PROCESSED,
        ViolationRecord.Status.PROCESSED: ViolationRecord.Status.PROCESSED,
    }
    return status_map.get(text)


def get_user_or_404(user_id):
    # 获取用户对象
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None


def update_user_fields(user, data):
    # 更新用户字段
    user.phone = str(data.get("phone", user.phone)).strip()
    user.email = str(data.get("email", user.email)).strip()

    role = str(data.get("role", user.role)).strip()
    if role and role in {User.Role.ADMIN, User.Role.AUDITOR, User.Role.USER}:
        user.role = role

    is_active = parse_bool(data.get("is_active"))
    if is_active is not None:
        user.is_active = is_active

    return user


@require_http_methods(["GET"])
def health_check(request):
    # 健康检查
    return json_success(
        {
            "service": "seatbelt-detection",
            "status": "ok",
        },
        message="seatbelt backend is running",
    )


@require_http_methods(["GET"])
def dashboard_view(request):
    # 首页统计
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    task_queryset = DetectTask.objects.select_related("user")
    violation_queryset = ViolationRecord.objects.select_related("task", "user", "auditor")
    if not is_staff_user(user):
        task_queryset = task_queryset.filter(user=user)
        violation_queryset = violation_queryset.filter(user=user)

    recent_limit = max(1, min(parse_int(request.GET.get("limit"), 5), 20))
    completed_task_queryset = task_queryset.filter(status=DetectTask.Status.COMPLETED)
    wear_task_queryset = completed_task_queryset.filter(has_violation=False, result_count__gt=0)
    no_wear_task_queryset = completed_task_queryset.filter(has_violation=True)
    pending_violation_queryset = violation_queryset.filter(status=ViolationRecord.Status.PENDING_REVIEW)
    dashboard_violation_queryset = violation_queryset.filter(
        status__in=[ViolationRecord.Status.PROCESSED, ViolationRecord.Status.REJECTED]
    )
    today_stats = build_today_detection_stats(user)
    data = {
        **today_stats,
        "total_count": task_queryset.count(),
        "today_count": today_stats["today_detection_total"],
        "pending_violation_count": pending_violation_queryset.count(),
        "violation_count": dashboard_violation_queryset.count(),
        "wear_count": wear_task_queryset.count(),
        "no_wear_count": no_wear_task_queryset.count(),
        "task_total": task_queryset.count(),
        "task_completed_total": completed_task_queryset.count(),
        "task_running_total": task_queryset.filter(status=DetectTask.Status.RUNNING).count(),
        "task_failed_total": task_queryset.filter(status=DetectTask.Status.FAILED).count(),
        "violation_total": dashboard_violation_queryset.count(),
        "pending_review_total": pending_violation_queryset.count(),
        "user_total": User.objects.filter(is_active=True).count() if is_staff_user(user) else 1,
        "recent_tasks": [
            serialize_task(item, request, include_results=False)
            for item in task_queryset.order_by("-created_at")[:recent_limit]
        ],
        "recent_violations": [
            serialize_violation(item, request)
            for item in violation_queryset.order_by("-created_at")[:recent_limit]
        ],
    }
    write_query_log(
        request,
        query_module="dashboard",
        query_params={"limit": recent_limit},
        result_count=len(data["recent_tasks"]) + len(data["recent_violations"]),
    )
    return json_success(data)


@csrf_exempt
@require_http_methods(["POST"])
def register_view(request):
    # 用户注册
    data = get_request_data(request)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()
    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()

    if not username or not password:
        return json_error("用户名和密码不能为空")
    if len(password) < 6:
        return json_error("密码长度不能少于6位")
    if confirm_password and password != confirm_password:
        return json_error("两次密码不一致")
    if User.objects.filter(username=username).exists():
        return json_error("用户名已存在")

    user = User.objects.create_user(
        username=username,
        password=password,
        phone=phone,
        email=email,
        role=User.Role.USER,
    )
    payload = {**serialize_user(user), **build_token_payload(user)}
    write_operation_log(request, "register", "user", user.id, f"username={user.username}")
    return json_success(payload, message="注册成功", status=201)


@csrf_exempt
@require_http_methods(["POST"])
def login_view(request):
    # 用户登录
    data = get_request_data(request)
    account = str(data.get("account", "")).strip()
    username = str(data.get("username", "")).strip()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", "")).strip()
    login_value = account or username or phone

    if not login_value or not password:
        return json_error("账号和密码不能为空")

    user = None
    if is_valid_phone(login_value):
        try:
            matched_user = User.objects.get(phone=login_value)
        except User.DoesNotExist:
            matched_user = None
        if matched_user is not None:
            user = authenticate(request, username=matched_user.username, password=password)
    if user is None:
        user = authenticate(request, username=login_value, password=password)
    if user is None:
        return json_error("账号或密码错误", 401, 401)
    if not user.is_active:
        return json_error("用户已被禁用", 403, 403)

    payload = {**serialize_user(user), **build_token_payload(user)}
    write_operation_log(request, "login", "user", user.id, f"account={login_value}")
    return json_success(payload, message="登录成功")


@csrf_exempt
@require_http_methods(["POST"])
def miniapp_register_view(request):
    # 小程序用户注册
    data = get_request_data(request)
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()

    if not is_valid_phone(phone):
        return json_error("请输入有效手机号")
    if not password:
        return json_error("密码不能为空")
    if len(password) < 6:
        return json_error("密码长度不能少于6位")
    if confirm_password and password != confirm_password:
        return json_error("两次密码不一致")
    if User.objects.filter(phone=phone).exists():
        return json_error("手机号已注册")

    user = User.objects.create_user(
        username=build_client_username(phone),
        password=password,
        phone=phone,
        role=User.Role.USER,
    )
    payload = {
        **serialize_user_with_plate_bindings(user),
        **build_token_payload(user),
        "need_bind_phone": not bool(user.phone),
        "phone_bound": bool(user.phone),
    }
    write_operation_log(request, "miniapp_register", "user", user.id, f"phone={phone}")
    return json_success(payload, message="注册成功", status=201)


@csrf_exempt
@require_http_methods(["POST"])
def miniapp_login_view(request):
    # 小程序登录
    data = get_request_data(request)
    account = str(data.get("account", "")).strip()
    password = str(data.get("password", "")).strip()

    if not account or not password:
        return json_error("账号和密码不能为空")

    user = None
    if is_valid_phone(account):
        try:
            matched_user = User.objects.get(phone=account)
        except User.DoesNotExist:
            matched_user = None
        if matched_user is not None:
            user = authenticate(request, username=matched_user.username, password=password)
    if user is None:
        user = authenticate(request, username=account, password=password)
    if user is None:
        return json_error("账号或密码错误", 401, 401)
    if not user.is_active:
        return json_error("用户已被禁用", 403, 403)

    payload = {
        **serialize_user_with_plate_bindings(user),
        **build_token_payload(user),
    }
    write_operation_log(request, "miniapp_login", "user", user.id, f"account={account}")
    return json_success(payload, message="登录成功")


@csrf_exempt
@require_http_methods(["POST"])
def miniapp_wx_login_view(request):
    data = get_request_data(request)
    code = str(data.get("code", "")).strip()
    if not code:
        return json_error("code不能为空")

    try:
        session_data = wechat_code_to_session(code)
    except ValueError as exc:
        return json_error(str(exc))

    openid = str(session_data.get("openid", "")).strip()
    if not openid:
        return json_error("微信登录失败")

    user = User.objects.filter(wx_openid=openid).first()
    created = False
    if user is None:
        user = User.objects.create_user(
            username=build_wechat_username(openid),
            password=None,
            role=User.Role.USER,
            wx_openid=openid,
        )
        created = True

    if not user.is_active:
        return json_error("鐢ㄦ埛宸茶绂佺敤", 403, 403)

    payload = {
        **serialize_user_with_plate_bindings(user),
        **build_token_payload(user),
        "need_bind_phone": not bool(user.phone),
        "phone_bound": bool(user.phone),
    }
    write_operation_log(
        request,
        "miniapp_wx_login",
        "user",
        user.id,
        f"openid={openid};created={int(created)}",
    )
    return json_success(payload, message="success")


@csrf_exempt
@require_http_methods(["POST"])
def miniapp_bind_phone_view(request):
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    data = get_request_data(request)
    phone_code = str(data.get("phone_code") or data.get("code") or "").strip()
    password = str(data.get("password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()

    if not phone_code:
        return json_error("phone_code不能为空")
    if not password:
        return json_error("密码不能为空")
    if len(password) < 6:
        return json_error("密码长度不能少于6位")
    if confirm_password and confirm_password != password:
        return json_error("两次密码不一致")

    try:
        phone_info = wechat_code_to_phone_info(phone_code)
    except ValueError as exc:
        return json_error(str(exc))

    phone = str(phone_info.get("phone", "")).strip()
    if not is_valid_phone(phone):
        return json_error("微信返回的手机号无效")
    existing_user = User.objects.filter(phone=phone).exclude(pk=user.pk).first()
    if existing_user is not None:
        try:
            user = merge_wechat_user_into_existing_user(
                user,
                existing_user,
                phone=phone,
                password=password,
            )
        except ValueError as exc:
            return json_error(str(exc))
    else:
        user.phone = phone
        user.set_password(password)
        user.save(update_fields=["phone", "password"])

    payload = {
        **serialize_user_with_plate_bindings(user),
        **build_token_payload(user),
        "need_bind_phone": False,
        "phone_bound": True,
    }
    write_operation_log(request, "miniapp_bind_phone", "user", user.id, f"phone={phone}")
    return json_success(payload, message="绑定成功")


@csrf_exempt
@require_http_methods(["POST"])
def refresh_token_view(request):
    # 刷新令牌
    data = get_request_data(request)
    refresh_token = str(data.get("refresh_token", "")).strip()
    if not refresh_token:
        return json_error("refresh_token不能为空")

    try:
        payload = decode_token(refresh_token, expected_type="refresh")
        user = User.objects.get(pk=payload["user_id"], is_active=True)
    except (JwtAuthError, User.DoesNotExist) as exc:
        return json_error(str(exc), 401, 401)

    access_token = create_access_token(user)
    write_operation_log(request, "refresh_token", "user", user.id, f"username={user.username}")
    return json_success(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TOKEN_EXPIRES_IN,
        },
        message="刷新成功",
    )


@csrf_exempt
@require_http_methods(["POST"])
def logout_view(request):
    # 退出登录
    user = None
    try:
        user = get_request_user(request)
    except JwtAuthError:
        pass
    write_operation_log(request, "logout", "user", getattr(user, "id", None), "")
    return json_success(message="退出成功")


@require_http_methods(["GET"])
def me_view(request):
    # 当前用户
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response
    return json_success(serialize_user(user))


@require_http_methods(["GET"])
def miniapp_me_view(request):
    # 小程序当前用户
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response
    return json_success(
        {
            "user": serialize_user(user),
            "bound_plates": [serialize_plate_binding(item) for item in get_user_active_plate_bindings(user)],
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def miniapp_plate_list_create(request):
    # 小程序车牌绑定列表和创建
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    if request.method == "GET":
        data = [serialize_plate_binding(item) for item in get_user_active_plate_bindings(user)]
        return json_success(data)

    data = get_request_data(request)
    plate_text = normalize_plate_text(data.get("plate_text", ""))
    if not plate_text:
        return json_error("车牌号不能为空")

    binding = UserPlateBinding.objects.filter(user=user, plate_text=plate_text).first()
    if binding is not None:
        if not binding.is_active:
            binding.is_active = True
            binding.save(update_fields=["is_active", "updated_at"])
            write_operation_log(request, "miniapp_bind_plate", "ser_plate_binding", binding.id, plate_text)
        return json_success(serialize_plate_binding(binding), message="绑定成功")

    binding = UserPlateBinding.objects.create(
        user=user,
        plate_text=plate_text,
        is_active=True,
    )
    write_operation_log(request, "miniapp_bind_plate", "ser_plate_binding", binding.id, plate_text)
    return json_success(serialize_plate_binding(binding), message="绑定成功", status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def miniapp_plate_delete(request, binding_id):
    # 小程序解绑车牌
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    try:
        binding = UserPlateBinding.objects.get(pk=binding_id, user=user)
    except UserPlateBinding.DoesNotExist:
        return json_error("车牌绑定不存在", 404, 404)

    binding.is_active = False
    binding.save(update_fields=["is_active", "updated_at"])
    write_operation_log(request, "miniapp_unbind_plate", "ser_plate_binding", binding.id, binding.plate_text)
    return json_success(
        {
            "id": binding.id,
            "plate_text": binding.plate_text,
            "is_active": binding.is_active,
        },
        message="解绑成功",
    )


@require_http_methods(["GET"])
def miniapp_violation_list(request):
    # 小程序违法记录列表
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    bound_plates = list(get_user_active_plate_bindings(user).values_list("plate_text", flat=True))
    if not bound_plates:
        return json_success(
            {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": max(1, min(parse_int(request.GET.get("page_size"), 10), 50)),
                "bound_plates": [],
            }
        )

    queryset = ViolationRecord.objects.select_related("task", "result", "object", "user", "auditor").filter(
        plate_text__in=bound_plates
    )
    plate_text = normalize_plate_text(request.GET.get("plate_text", ""))
    review_status = normalize_violation_query_status(request.GET.get("status", "").strip())
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if plate_text:
        queryset = queryset.filter(plate_text=plate_text)
    if review_status is not None:
        queryset = queryset.filter(status=review_status)
    queryset = apply_date_filters(queryset, date_from, date_to)

    total = queryset.count()
    page = max(1, parse_int(request.GET.get("page"), 1))
    page_size = max(1, min(parse_int(request.GET.get("page_size"), 10), 50))
    start = (page - 1) * page_size
    end = start + page_size
    items = [serialize_violation(item, request) for item in queryset.order_by("-created_at")[start:end]]
    write_query_log(
        request,
        query_module="miniapp_violation_record",
        query_params=dict(request.GET),
        result_count=len(items),
    )
    return json_success(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "bound_plates": bound_plates,
        }
    )


@require_http_methods(["GET"])
def miniapp_violation_detail(request, violation_id):
    # 小程序违法记录详情
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    bound_plates = list(get_user_active_plate_bindings(user).values_list("plate_text", flat=True))
    if not bound_plates:
        return json_error("当前账号未绑定车牌", 403, 403)

    try:
        violation = ViolationRecord.objects.select_related("task", "result", "object", "user", "auditor").get(
            Q(pk=violation_id),
            Q(plate_text__in=bound_plates),
        )
    except ViolationRecord.DoesNotExist:
        return json_error("违法记录不存在", 404, 404)

    write_query_log(request, query_module="miniapp_violation_detail", query_params={"id": violation_id}, result_count=1)
    return json_success(serialize_violation(violation, request))


@csrf_exempt
@require_http_methods(["POST"])
def miniapp_violation_review(request, violation_id):
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    bound_plates = list(get_user_active_plate_bindings(user).values_list("plate_text", flat=True))
    if not bound_plates:
        return json_error("当前账号未绑定车牌", 403, 403)

    try:
        violation = ViolationRecord.objects.select_related("task", "result", "object", "user", "auditor").get(
            Q(pk=violation_id),
            Q(plate_text__in=bound_plates),
        )
    except ViolationRecord.DoesNotExist:
        return json_error("违法记录不存在", 404, 404)

    violation.status = ViolationRecord.Status.PENDING_REVIEW
    violation.auditor = None
    violation.audit_time = None
    violation.audit_remark = ""
    violation.handled_time = None
    violation.handled_remark = ""
    violation.save(
        update_fields=[
            "status",
            "auditor",
            "audit_time",
            "audit_remark",
            "handled_time",
            "handled_remark",
            "updated_at",
        ]
    )
    write_operation_log(request, "miniapp_review_apply", "violation_record", violation.id, f"status={violation.status}")
    return json_success({"id": violation.id, "status": 1})


@csrf_exempt
@require_http_methods(["POST"])
def change_password_view(request):
    # 修改密码
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    data = get_request_data(request)
    old_password = str(data.get("old_password", "")).strip()
    new_password = str(data.get("new_password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()

    if not old_password or not new_password:
        return json_error("旧密码和新密码不能为空")
    if not user.check_password(old_password):
        return json_error("旧密码错误")
    if len(new_password) < 6:
        return json_error("新密码长度不能少于6位")
    if confirm_password and new_password != confirm_password:
        return json_error("两次密码不一致")
    if old_password == new_password:
        return json_error("新密码不能和旧密码相同")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    payload = {**serialize_user(user), **build_token_payload(user)}
    write_operation_log(request, "change_password", "user", user.id, f"username={user.username}")
    return json_success(payload, message="密码修改成功")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def detection_list_create(request):
    # 识别任务列表和创建
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    if request.method == "GET":
        queryset = DetectTask.objects.select_related("user").prefetch_related("results")
        if not is_staff_user(user):
            queryset = queryset.filter(user=user)

        status_value = request.GET.get("status", "").strip()
        task_type = request.GET.get("task_type", "").strip()
        username = request.GET.get("username", "").strip()
        has_violation = parse_bool(request.GET.get("has_violation"))
        review_status = normalize_violation_query_status(request.GET.get("review_status", "").strip())
        plate_text = request.GET.get("plate_text", "").strip()
        task_no = request.GET.get("task_no", "").strip()
        source_name = request.GET.get("source_name", "").strip()
        date_from = request.GET.get("date_from", "").strip()
        date_to = request.GET.get("date_to", "").strip()

        if status_value:
            queryset = queryset.filter(status=status_value)
        if task_type:
            queryset = queryset.filter(task_type=task_type)
        if username and is_staff_user(user):
            queryset = queryset.filter(user__username__icontains=username)
        if has_violation is not None:
            queryset = queryset.filter(has_violation=has_violation)
        if review_status is not None:
            queryset = queryset.filter(violations__status=review_status).distinct()
        if plate_text:
            queryset = queryset.filter(detect_objects__plate_text__icontains=plate_text).distinct()
        if task_no:
            queryset = queryset.filter(task_no__icontains=task_no)
        if source_name:
            queryset = queryset.filter(source_name__icontains=source_name)
        queryset = apply_date_filters(queryset, date_from, date_to)

        data = [serialize_task(task, request, include_results=False) for task in queryset]
        write_query_log(request, query_module="detect_task", query_params=dict(request.GET), result_count=len(data))
        return json_success(data)

    upload = request.FILES.get("file")
    if upload is None:
        return json_error("请使用multipart/form-data上传file文件")

    notes = request.POST.get("notes", "").strip()
    content_type = upload.content_type or ""
    file_suffix = Path(upload.name).suffix.lower()
    task_type = (
        DetectTask.TaskType.VIDEO
        if content_type.startswith("video/") or file_suffix in {".mp4", ".avi", ".mov", ".mkv"}
        else DetectTask.TaskType.IMAGE
    )

    task = DetectTask.objects.create(
        task_no=build_task_no(),
        user=user,
        task_type=task_type,
        source_name=upload.name,
        source_file=upload,
        status=DetectTask.Status.RUNNING,
        progress=0,
        started_at=timezone.now(),
        notes=notes,
        metadata={"content_type": content_type, "size_bytes": upload.size},
    )
    write_operation_log(request, "create_task", "detect_task", task.id, f"task_no={task.task_no}")

    try:
        result = SeatbeltDetectionService().analyze(task)
        task.status = DetectTask.Status.COMPLETED
        task.progress = 100
        task.result_count = int(result.get("result_count", task.result_count or 1))
        task.processed_frames = int(result.get("processed_frames", task.processed_frames or task.result_count))
        task.total_frames = int(result.get("total_frames", task.total_frames or task.result_count))
        task.duration_ms = result.get("duration_ms", task.duration_ms)
        task.violation_count = int(result.get("violation_count", 0))
        task.has_violation = bool(result.get("has_violation", False))
        task.finished_at = timezone.now()
        task.save(
            update_fields=[
                "status",
                "progress",
                "result_count",
                "processed_frames",
                "total_frames",
                "duration_ms",
                "violation_count",
                "has_violation",
                "finished_at",
                "notes",
                "metadata",
                "updated_at",
            ]
        )
        increment_daily_detection_stat(user, stat_date=timezone.localdate())
        write_operation_log(request, "detect_completed", "detect_task", task.id, f"result_count={task.result_count}")
    except ModelRuntimeError as exc:
        task.status = DetectTask.Status.FAILED
        task.error_message = str(exc)
        task.finished_at = timezone.now()
        task.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        write_operation_log(request, "detect_failed", "detect_task", task.id, str(exc))
        return JsonResponse(
            {"code": 503, "message": str(exc), "data": serialize_task(task, request, include_results=True)},
            status=503,
        )
    except Exception as exc:
        task.status = DetectTask.Status.FAILED
        task.error_message = str(exc)
        task.finished_at = timezone.now()
        task.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        logger.exception("Unexpected detection error task_id=%s", task.id)
        write_operation_log(request, "detect_failed", "detect_task", task.id, str(exc))
        return JsonResponse(
            {"code": 500, "message": "检测失败", "data": serialize_task(task, request, include_results=True)},
            status=500,
        )

    task = DetectTask.objects.select_related("user").prefetch_related(
        "results__detect_objects",
        "results__violations__task",
        "results__violations__user",
        "results__violations__auditor",
    ).get(pk=task.pk)
    return json_success(serialize_task(task, request, include_results=True), message="检测完成", status=201)


@require_http_methods(["GET"])
def detection_detail(request, record_id):
    # 识别任务详情
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    try:
        task = DetectTask.objects.select_related("user").prefetch_related(
            "results__detect_objects",
            "results__violations__task",
            "results__violations__user",
            "results__violations__auditor",
        ).get(pk=record_id)
    except DetectTask.DoesNotExist:
        return json_error("记录不存在", 404, 404)

    if not is_staff_user(user) and task.user_id != user.id:
        return json_error("无权查看该记录", 403, 403)

    write_query_log(request, query_module="detect_task_detail", query_params={"id": record_id}, result_count=1)
    return json_success(serialize_task(task, request, include_results=True))


@require_http_methods(["GET"])
def violation_list(request):
    # 违规记录列表
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    queryset = ViolationRecord.objects.select_related("task", "result", "object", "user", "auditor")
    if not is_staff_user(user):
        queryset = queryset.filter(user=user)

    username = request.GET.get("username", "").strip()
    plate_text = request.GET.get("plate_text", "").strip()
    review_status = normalize_violation_query_status(request.GET.get("status", "").strip())
    task_status = request.GET.get("task_status", "").strip()
    violation_type = request.GET.get("violation_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if username and is_staff_user(user):
        queryset = queryset.filter(user__username__icontains=username)
    if plate_text:
        queryset = queryset.filter(plate_text__icontains=plate_text)
    if review_status is not None:
        queryset = queryset.filter(status=review_status)
    if task_status:
        queryset = queryset.filter(task__status=task_status)
    if violation_type:
        queryset = queryset.filter(violation_type=violation_type)
    queryset = apply_date_filters(queryset, date_from, date_to)

    data = [serialize_violation(item, request) for item in queryset]
    write_query_log(request, query_module="violation_record", query_params=dict(request.GET), result_count=len(data))
    return json_success(data)


@require_http_methods(["GET"])
def violation_detail(request, violation_id):
    # 违规记录详情
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    try:
        violation = ViolationRecord.objects.select_related("task", "result", "object", "user", "auditor").get(
            pk=violation_id
        )
    except ViolationRecord.DoesNotExist:
        return json_error("违规记录不存在", 404, 404)

    if not is_staff_user(user) and violation.user_id != user.id:
        return json_error("无权查看该记录", 403, 403)

    write_query_log(request, query_module="violation_detail", query_params={"id": violation_id}, result_count=1)
    return json_success(serialize_violation(violation, request))


@csrf_exempt
@require_http_methods(["POST"])
def violation_review(request, violation_id):
    # 审核违规
    user, error_response = require_staff_user(request)
    if error_response:
        return error_response

    try:
        violation = ViolationRecord.objects.select_related("task", "result", "object", "user", "auditor").get(
            pk=violation_id
        )
    except ViolationRecord.DoesNotExist:
        return json_error("违规记录不存在", 404, 404)

    data = get_request_data(request)
    action = normalize_review_action(data.get("status") or data.get("action"))
    audit_remark = str(data.get("audit_remark", "")).strip()
    handled_remark = str(data.get("handled_remark", "")).strip()
    now = timezone.now()

    if action == ViolationRecord.Status.CONFIRMED:
        violation.status = ViolationRecord.Status.CONFIRMED
        violation.auditor = user
        violation.audit_time = now
        violation.audit_remark = audit_remark
    elif action == ViolationRecord.Status.REJECTED:
        violation.status = ViolationRecord.Status.REJECTED
        violation.auditor = user
        violation.audit_time = now
        violation.audit_remark = audit_remark
    elif action == ViolationRecord.Status.PROCESSED:
        violation.status = ViolationRecord.Status.PROCESSED
        if violation.auditor_id is None:
            violation.auditor = user
        if violation.audit_time is None:
            violation.audit_time = now
        if audit_remark:
            violation.audit_remark = audit_remark
        violation.handled_time = now
        violation.handled_remark = handled_remark
    else:
        return json_error("审核动作无效")

    violation.save()
    write_operation_log(
        request,
        "review_violation",
        "violation_record",
        violation.id,
        f"status={violation.status}",
    )
    return json_success(serialize_violation(violation, request), message="处理成功")


@require_http_methods(["GET"])
def query_log_list(request):
    # 查询日志列表
    _, error_response = require_staff_user(request)
    if error_response:
        return error_response

    queryset = QueryLog.objects.select_related("user")
    username = request.GET.get("username", "").strip()
    query_module = request.GET.get("query_module", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if username:
        queryset = queryset.filter(user__username__icontains=username)
    if query_module:
        queryset = queryset.filter(query_module=query_module)
    queryset = apply_date_filters(queryset, date_from, date_to)

    data = [serialize_query_log(item) for item in queryset]
    write_query_log(request, query_module="query_log", query_params=dict(request.GET), result_count=len(data))
    return json_success(data)


@require_http_methods(["GET"])
def operation_log_list(request):
    # 操作日志列表
    _, error_response = require_staff_user(request)
    if error_response:
        return error_response

    queryset = OperationLog.objects.select_related("user")
    username = request.GET.get("username", "").strip()
    operation_type = request.GET.get("operation_type", "").strip()
    target_type = request.GET.get("target_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if username:
        queryset = queryset.filter(user__username__icontains=username)
    if operation_type:
        queryset = queryset.filter(operation_type=operation_type)
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    queryset = apply_date_filters(queryset, date_from, date_to)

    data = [serialize_operation_log(item) for item in queryset]
    write_query_log(request, query_module="operation_log", query_params=dict(request.GET), result_count=len(data))
    return json_success(data)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def user_list_create(request):
    # 系统用户列表和创建
    current_user, error_response = require_staff_user(request)
    if error_response:
        return error_response

    if request.method == "GET":
        queryset = User.objects.all().order_by("-created_at")
        username = request.GET.get("username", "").strip()
        role = request.GET.get("role", "").strip()
        is_active = parse_bool(request.GET.get("is_active"))
        date_from = request.GET.get("date_from", "").strip()
        date_to = request.GET.get("date_to", "").strip()

        if username:
            queryset = queryset.filter(username__icontains=username)
        if role:
            queryset = queryset.filter(role=role)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        queryset = apply_date_filters(queryset, date_from, date_to)

        data = [serialize_user(item) for item in queryset]
        write_query_log(request, query_module="system_user", query_params=dict(request.GET), result_count=len(data))
        return json_success(data)

    if current_user.role != User.Role.ADMIN:
        return json_error("仅管理员可操作", 403, 403)

    data = get_request_data(request)
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()
    role = str(data.get("role", User.Role.USER)).strip() or User.Role.USER

    if not username or not password:
        return json_error("用户名和密码不能为空")
    if len(password) < 6:
        return json_error("密码长度不能少于6位")
    if confirm_password and password != confirm_password:
        return json_error("两次密码不一致")
    if role not in {User.Role.ADMIN, User.Role.AUDITOR, User.Role.USER}:
        return json_error("角色无效")
    if User.objects.filter(username=username).exists():
        return json_error("用户名已存在")

    user = User.objects.create_user(
        username=username,
        password=password,
        phone=str(data.get("phone", "")).strip(),
        email=str(data.get("email", "")).strip(),
        role=role,
        is_active=parse_bool(data.get("is_active")) if parse_bool(data.get("is_active")) is not None else True,
    )
    write_operation_log(request, "create_user", "user", user.id, f"username={user.username}")
    return json_success(serialize_user(user), message="创建成功", status=201)


@csrf_exempt
@require_http_methods(["GET", "PUT", "POST"])
def user_detail_update(request, user_id):
    # 系统用户详情和修改
    current_user, error_response = require_staff_user(request)
    if error_response:
        return error_response

    user = get_user_or_404(user_id)
    if user is None:
        return json_error("用户不存在", 404, 404)

    if request.method == "GET":
        write_query_log(request, query_module="system_user_detail", query_params={"id": user_id}, result_count=1)
        return json_success(serialize_user(user))

    if current_user.role != User.Role.ADMIN:
        return json_error("仅管理员可操作", 403, 403)

    data = get_request_data(request)
    user = update_user_fields(user, data)
    user.save()
    write_operation_log(request, "update_user", "user", user.id, f"username={user.username}")
    return json_success(serialize_user(user), message="更新成功")


@csrf_exempt
@require_http_methods(["POST"])
def user_reset_password(request, user_id):
    # 重置用户密码
    current_user, error_response = require_admin_user(request)
    if error_response:
        return error_response

    user = get_user_or_404(user_id)
    if user is None:
        return json_error("用户不存在", 404, 404)

    data = get_request_data(request)
    new_password = str(data.get("new_password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()

    if not new_password:
        return json_error("新密码不能为空")
    if len(new_password) < 6:
        return json_error("新密码长度不能少于6位")
    if confirm_password and new_password != confirm_password:
        return json_error("两次密码不一致")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    write_operation_log(request, "reset_password", "user", user.id, f"username={user.username}")
    return json_success({"id": user.id, "username": user.username}, message="重置成功")


@require_http_methods(["GET"])
def object_image(request, object_id):
    # 目标截图
    user, error_response = get_auth_user_or_response(request)
    if error_response:
        return error_response

    try:
        detect_object = DetectObject.objects.select_related("task").get(pk=object_id)
    except DetectObject.DoesNotExist:
        return json_error("目标不存在", 404, 404)

    if not is_staff_user(user) and detect_object.task.user_id != user.id:
        return json_error("无权查看该图片", 403, 403)
    if not detect_object.crop_data:
        return json_error("目标图片不存在", 404, 404)

    return HttpResponse(bytes(detect_object.crop_data), content_type=detect_object.crop_content_type)
