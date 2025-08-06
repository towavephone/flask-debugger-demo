def get_success(data=None, msg=None, code=200, **args) -> dict:
    return {"error": False, "code": code, "msg": msg, "data": data, **args}


def get_error(code=501, msg=None, data=None, **args) -> dict:
    return {"error": True, "code": code, "msg": msg, "data": data, **args}, 500
