import json
from bson import ObjectId
from datetime import datetime


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)  # 将 ObjectId 转换为字符串

        if isinstance(obj, datetime):
            return obj.strftime(
                "%Y-%m-%d %H:%M:%S"
            )  # 将 datetime 转换为 ISO 格式字符串

        return super().default(obj)
