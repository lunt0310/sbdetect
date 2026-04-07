import base64
import hashlib
import hmac
import json
import time

from django.conf import settings

from ..business.models import User


ACCESS_TOKEN_EXPIRES_IN = 2 * 60 * 60
REFRESH_TOKEN_EXPIRES_IN = 7 * 24 * 60 * 60


class JwtAuthError(Exception):
    # JWT认证异常
    pass


def create_access_token(user):
    # 生成访问令牌
    return _create_token(user, "access", ACCESS_TOKEN_EXPIRES_IN)


def create_refresh_token(user):
    # 生成刷新令牌
    return _create_token(user, "refresh", REFRESH_TOKEN_EXPIRES_IN)


def build_token_payload(user):
    # 组装令牌数据
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXPIRES_IN,
    }


def decode_token(token, expected_type=None):
    # 解析令牌
    try:
        header_part, payload_part, signature_part = token.split(".")
    except ValueError as exc:
        raise JwtAuthError("令牌格式错误") from exc

    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise JwtAuthError("令牌签名无效")

    payload = _json_loads(_b64decode(payload_part))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise JwtAuthError("令牌已过期")
    if expected_type and payload.get("token_type") != expected_type:
        raise JwtAuthError("令牌类型错误")
    return payload


def get_bearer_token(request):
    # 提取Bearer令牌
    auth_header = request.META.get("HTTP_AUTHORIZATION", "").strip()
    if not auth_header:
        return ""
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    return parts[1].strip()


def get_request_user(request):
    # 从令牌获取用户
    token = get_bearer_token(request)
    if not token:
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return user
        return None

    payload = decode_token(token, expected_type="access")
    user_id = payload.get("user_id")
    if not user_id:
        raise JwtAuthError("令牌用户无效")
    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist as exc:
        raise JwtAuthError("用户不存在或已禁用") from exc


def _create_token(user, token_type, expires_in):
    # 构造JWT
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "token_type": token_type,
        "iat": now,
        "exp": now + expires_in,
    }
    header_part = _b64encode(_json_dumps(header))
    payload_part = _b64encode(_json_dumps(payload))
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    signature_part = _sign(signing_input)
    return f"{header_part}.{payload_part}.{signature_part}"


def _sign(data):
    # 计算签名
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), data, hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(data):
    # base64编码
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data):
    # base64解码
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _json_dumps(data):
    # JSON编码
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _json_loads(data):
    # JSON解码
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)
