from .jwt_utils import JwtAuthError, get_request_user
from ..business.models import OperationLog, QueryLog


def get_user(request):
    # 获取用户
    try:
        return get_request_user(request)
    except JwtAuthError:
        return None


def write_query_log(request, query_module, query_params, result_count):
    # 写查询日志
    QueryLog.objects.create(
        user=get_user(request),
        query_module=query_module,
        query_params=query_params,
        result_count=result_count,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )


def write_operation_log(request, operation_type, target_type="", target_id=None, detail=""):
    # 写操作日志
    OperationLog.objects.create(
        user=get_user(request),
        operation_type=operation_type,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        request_method=request.method,
        request_path=request.path[:255],
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
