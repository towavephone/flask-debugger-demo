import functools
import traceback
import json

from flask import request, Response, current_app
from utils import http_response
from utils.encode_util import CustomJSONEncoder


def request_wrapper():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                data = func(*args, **kwargs)

                if isinstance(data, Response):
                    return data

                return http_response.get_success(data)
            except Exception as ex:
                current_app.logger.error(repr(ex))
                current_app.logger.error(traceback.format_exc())
                return http_response.get_error(msg=repr(ex))

        return wrapper

    return decorator


def parse_param(data):
    try:
        return json.loads(data)
    except Exception as ex:
        pass

    # try:
    #     data = xmltodict.parse(data)
    #     data = py_.get(data, "root")
    #     return data
    # except Exception as ex:
    #     pass

    return data


class EmptyValue:
    """自定义空值类，用于区分不同场景的空值"""

    def __repr__(self):
        return "EmptyValue"  # 打印时更易识别


def get_param(name, default=None, type=None, method="GET"):
    data = {}
    if method == "GET":
        data = request.args
    elif method == "POST":
        data = request.data
        data = parse_param(data)
    return get_data_param(data=data, name=name, default=default, type_=type)


def get_post_param(name, default=None, type=None):
    return get_param(name, default=default, type=type, method="POST")


class MissingParameterError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


def get_data_param(data, name, default=None, type_=None):
    value = data.get(name, default)

    if value is not None and type_:
        value = type_(value)

    if value is None and name not in data:
        raise MissingParameterError("Missing required parameter: {}".format(name))

    return value


def get_json_result(result):
    # TODO 待优化，这里最好写成递归的，避免 json 转换损耗
    return json.loads(json.dumps(result, cls=CustomJSONEncoder))
