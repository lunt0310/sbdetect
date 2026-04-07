from django.http import HttpResponse


class SimpleCorsMiddleware:
    # 处理跨域预检
    def __init__(self, get_response):
        # 保存下一个处理器
        self.get_response = get_response

    def __call__(self, request):
        # 统一处理请求
        if request.path.startswith("/api/") and request.method == "OPTIONS":
            response = HttpResponse(status=200)
            return self._set_cors_headers(response)

        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response = self._set_cors_headers(response)
        return response

    def _set_cors_headers(self, response):
        # 写入跨域头
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With"
        response["Access-Control-Max-Age"] = "86400"
        return response
