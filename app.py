import logging
import time
import signal
import sys
import os
import importlib
import traceback

from flask import Flask, request, g
from flask_restful import Resource, Api
from flask_cors import CORS

# from utils.encode_util import CustomJSONEncoder
from debug_toolbar.panels import register_mongo_listener


app = Flask(__name__)
CORS(app)
api = Api(app)
env = os.getenv("DEPLOY_ENV", "dev")
register_mongo_listener()


def exit_gracefully(*args):
    app.logger.info("Exiting gracefully...")
    try:
        if env == "prod":
            # not implemented yet
            pass
    except Exception as e:
        app.logger.error(str(e))
    finally:
        app.logger.info("Exiting...")
        sys.exit(0)


def init_logging():
    # 设置 logging
    LOG_FORMAT = "[%(asctime)s] %(levelname)s in %(pathname)s:%(lineno)d: %(message)s"
    root_handler = logging.StreamHandler()
    root_handler.setLevel(logging.DEBUG)
    root_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.basicConfig(level=logging.DEBUG, handlers=[root_handler])

    # 先移除原有的 handler，避免重复输出
    app.logger.handlers.clear()
    app.logger.addHandler(root_handler)
    app.logger.setLevel(logging.DEBUG)
    app.logger.propagate = False  # 关键：阻止日志向上传递


init_logging()

if not app.debug:
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(logging.DEBUG)

    # root logger 也复用
    logging.getLogger().handlers = gunicorn_logger.handlers
    logging.getLogger().setLevel(logging.DEBUG)

    app.logger.info(f"Start Backend Server, env: {env}")

    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)
else:
    # 覆盖 werkzeug 的请求日志方法
    import werkzeug.serving

    werkzeug.serving.WSGIRequestHandler.log_request = (
        lambda self, code="", size="": None
    )


class Home(Resource):
    @staticmethod
    def get():
        return "Backend Server is Up", 200


api.add_resource(Home, "/")


def is_route_file(filename):
    return filename.startswith("api") and filename.endswith(".py")


def mod_name_to_route(mod_name):
    parts = mod_name.split(".")

    last = parts[-1]
    if last == "api":
        # 只取前面的部分
        parts = parts[:-1]
    elif last.startswith("api_"):
        # 只保留 api_ 后的部分
        parts = parts[:-1] + [last[4:]]

    # 将所有 _ 替换成 /
    path_parts = []
    for part in parts:
        path_parts.extend(part.split("_"))

    # 拼接为路由路径
    route = "/" + "/".join(path_parts)
    return route


extra_files = []


def register_routes(package_path, package_name):
    for root, dirs, files in os.walk(package_path):
        for file in files:
            if is_route_file(file):
                try:
                    # 动态 import 路由文件
                    module_path = os.path.join(root, file)
                    extra_files.append(module_path)
                    rel_path = os.path.relpath(module_path, package_path)
                    mod_name = rel_path.replace(os.sep, ".")[:-3]  # 去掉 .py
                    full_mod_name = f"{package_name}.{mod_name}"
                    module = importlib.import_module(full_mod_name)
                    blueprint = getattr(module, "bp")
                    url_prefix = blueprint.url_prefix
                    if url_prefix:
                        url_prefix = "/api" + url_prefix
                    else:
                        url_prefix = "/api" + mod_name_to_route(mod_name)
                    app.register_blueprint(blueprint, url_prefix=url_prefix)
                except Exception as e:
                    logging.error(f"Failed to register route from {file}: {e}")
                    logging.error(traceback.format_exc())


package_name = ["apis", "bp"]
blueprints_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), *package_name)
# 注册所有 api 子模块
register_routes(blueprints_dir, ".".join(package_name))

# 重载观察文件
logging.info(f"watch extra files: {extra_files}")
os.environ["FLASK_RUN_EXTRA_FILES"] = ":".join(extra_files)

# 注册自定义编码器
# app.json_encoder = CustomJSONEncoder


@app.before_request
def before_request():
    g.start_time = time.time()
    app.logger.info(f"Request start: {request.method} {request.path}")


@app.after_request
def after_request(response):
    duration = (time.time() - g.start_time) * 1000
    logging.info(
        f"Request end: {request.method} {request.path} {response.status} {duration:.2f}ms"
    )
    return response


if app.debug:
    # flask_profiler
    # http://localhost:3004/flask-profiler
    import flask_profiler
    app.config["flask_profiler"] = {
        "enabled": True,
        "storage": {
            "engine": "sqlalchemy",
            "db_url": "sqlite:///flask_profiler.sql"
        },
        "ignore": [
            "^/static/.*",
            "^/_debug_toolbar/.*"
        ]
    }
    flask_profiler.init_app(app)

    # DebugToolbar
    # 1. 访问 http://localhost:3004/ 首页，可以看到 flask debug toolbar 页面
    # 2. 用 postman 或前端页面请求接口，请求的接口需要带上 ?_debug 参数
    # 3. 查看 flask debug toolbar 页面上的 History，即可看到请求历史以及对应的数据库语句
    # 4. 当然也支持直接访问接口 http://localhost:3004/api/path1/path2/path3/test?id=1&_debug
    from debug_toolbar import DevToolbar

    app.config["SECRET_KEY"] = "123456"
    app.config["DEBUG_TB_TEMPLATE_EDITOR_ENABLED"] = True
    app.config["DEBUG_TB_PROFILER_ENABLED"] = True
    app.config["DEBUG_TB_PANELS"] = (
        "debug_toolbar.panels.RequestHistoryPanel",  # 历史请求面板
        "debug_toolbar.panels.MongoDebugPanel",  # MongoDB 查询面板
        "flask_debugtoolbar.panels.sqlalchemy.SQLAlchemyDebugPanel",
        "flask_debugtoolbar.panels.route_list.RouteListDebugPanel",
        "flask_debugtoolbar.panels.logger.LoggingPanel",
        "flask_debugtoolbar.panels.profiler.ProfilerDebugPanel",
        "flask_debugtoolbar.panels.versions.VersionDebugPanel",
        "flask_debugtoolbar.panels.timer.TimerDebugPanel",
        "flask_debugtoolbar.panels.headers.HeaderDebugPanel",
        "flask_debugtoolbar.panels.request_vars.RequestVarsDebugPanel",
        "flask_debugtoolbar.panels.config_vars.ConfigVarsDebugPanel",
        "flask_debugtoolbar.panels.template.TemplateDebugPanel",
        "flask_debugtoolbar.panels.g.GDebugPanel",
    )
    DevToolbar(app)

    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        import debugpy

        DEBUG_PORT = 6534
        debugpy.listen(("0.0.0.0", DEBUG_PORT))
        # debugpy.wait_for_client()
        app.logger.info(f"Flask debug started, port is {DEBUG_PORT}")
