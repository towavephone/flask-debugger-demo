from flask_debugtoolbar.panels import DebugPanel
from collections import deque
from datetime import datetime
import time
from flask import render_template, g


# 存储历史请求 (内存中)
REQUEST_HISTORY = deque(maxlen=50)  # 限制最大记录数


class RequestHistoryPanel(DebugPanel):
    """显示历史请求的自定义面板"""

    name = "RequestHistory"
    has_content = True

    def nav_title(self):
        return "History"

    def nav_subtitle(self):
        return f"{len(REQUEST_HISTORY)} requests"

    def title(self):
        return "携带参数 ?_debug 的请求历史"

    def url(self):
        return ""

    def process_response(self, request, response):
        if "_debug" not in request.args:
            return

        # print(f"Process Request: {request.path}")

        # 记录请求数据
        duration = (time.time() - g.start_time) * 1000  # 毫秒
        request_data = {
            "id": len(REQUEST_HISTORY) + 1,
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration": duration,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mongo_queries": g.mongo_queries if hasattr(g, "mongo_queries") else [],
        }

        # 添加到历史队列
        REQUEST_HISTORY.appendleft(request_data)

    def content(self):
        context = self.context.copy()
        context.update(
            {
                "requests": REQUEST_HISTORY,
            }
        )
        return render_template("history_panel.html", **context)
