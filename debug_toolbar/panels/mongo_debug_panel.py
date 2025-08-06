from flask_debugtoolbar.panels import DebugPanel
from flask import render_template, has_request_context, request, g
from pymongo import monitoring
import time
import json
from bson import SON
import os
import re
from pydash import py_
from debug_toolbar.dev_toolbar import global_request_data


class MongoDebugPanel(DebugPanel):
    """显示MongoDB的自定义面板"""

    name = "MongoDB"
    has_content = True

    def nav_title(self):
        return "MongoDB"

    def nav_subtitle(self):
        queries = py_.get(global_request_data, "mongo_queries", [])
        return f"{len(queries)} queries"

    def title(self):
        return "所有 MongoDB 历史访问"

    def url(self):
        return ""

    def content(self):
        queries = py_.get(global_request_data, "mongo_queries", [])
        context = self.context.copy()
        context.update(
            {"queries": queries, "total_duration": sum(q["duration"] for q in queries)}
        )
        return render_template("mongo_panel.html", **context)


def format_mongo_shell_generic(shell: str, indent: int = 2) -> str:
    """
    通用 Mongo Shell/SQL 格式化器。
    适用于 db.xxx.xxx(...) 语句，支持链式调用，支持嵌套括号和换行缩进。
    """
    s = shell.strip()

    # 1. 用正则分割每个链式调用（.func(args)）
    parts = []
    bracket = 0
    last = 0
    for i, c in enumerate(s):
        if c == "(":
            bracket += 1
        elif c == ")":
            bracket -= 1
        elif c == "." and bracket == 0 and i > 0:
            parts.append(s[last:i])
            last = i
    parts.append(s[last:])

    # 2. 格式化每段 .func(args)
    formatted = ""
    first = True
    for p in parts:
        m = re.match(r"^(\w+\.)?(\w+)\((.*)\)$", p.strip(), re.DOTALL)
        if m:
            prefix, func, args = m.groups()
            # 尝试智能分割入参（按逗号分隔且支持嵌套对象/数组）
            arg_list = []
            depth = 0
            start = 0
            for i, c in enumerate(args):
                if c in "{[(":
                    depth += 1
                elif c in "}])":
                    depth -= 1
                elif c == "," and depth == 0:
                    arg_list.append(args[start:i].strip())
                    start = i + 1
            if args[start:].strip():
                arg_list.append(args[start:].strip())
            # 多参数多行缩进
            arg_fmt = ",\n".join(" " * indent + a for a in arg_list)
            line = f"{('.' if not first else '')}{func}(\n{arg_fmt}\n)"
        else:
            # 不规则部分原样输出
            line = p.strip()
        formatted += ("" if first else "\n") + line
        first = False

    return formatted


def bson_to_shell(val):
    """简易 BSON/SON/字典/列表转Mongo shell字符串。"""
    # 你可以用更健壮的 json_util，但简单情况直接 json.dumps
    # 注意 _id/ObjectId/Date 等类型复杂场景可引入 bson.json_util
    if isinstance(val, SON):
        val = dict(val)
    return json.dumps(val, ensure_ascii=False, default=str, indent=2)


def pymongo_cmd_to_shell(cmd):
    """
    cmd: dict or SON from pymongo monitoring CommandListener
    return: mongo shell string
    """
    d = dict(cmd)
    if "find" in d:
        # 查询
        collection = d["find"]
        filter_ = d.get("filter", d.get("query", {}))
        proj = d.get("projection")
        shell = f"db.{collection}.find({bson_to_shell(filter_)}"
        if proj:
            shell += f", {bson_to_shell(proj)}"
        shell += ")"
        if "sort" in d:
            shell += f".sort({bson_to_shell(dict(d['sort']))})"
        if "limit" in d:
            shell += f".limit({d['limit']})"
        if "skip" in d:
            shell += f".skip({d['skip']})"
        return shell

    elif "insert" in d:
        # 批量插入
        collection = d["insert"]
        docs = d.get("documents", [])
        if len(docs) == 1:
            return f"db.{collection}.insert({bson_to_shell(docs[0])})"
        else:
            return f"db.{collection}.insertMany({bson_to_shell(docs)})"

    elif "update" in d:
        # 批量或单条更新
        collection = d["update"]
        updates = d.get("updates", [])
        shells = []
        for upd in updates:
            q = upd.get("q", {})
            u = upd.get("u", {})
            multi = upd.get("multi", False)
            upsert = upd.get("upsert", False)
            opt = {}
            if upsert:
                opt["upsert"] = True
            if multi:
                call = "updateMany"
            else:
                call = "updateOne"
            opt_str = f", {bson_to_shell(opt)}" if opt else ""
            shells.append(
                f"db.{collection}.{call}({bson_to_shell(q)}, {bson_to_shell(u)}{opt_str})"
            )
        return ";\n".join(shells)

    elif "delete" in d:
        # 批量或单条删除
        collection = d["delete"]
        deletes = d.get("deletes", [])
        shells = []
        for dele in deletes:
            q = dele.get("q", {})
            limit = dele.get("limit", 0)
            if limit == 1:
                call = "deleteOne"
            else:
                call = "deleteMany"
            shells.append(f"db.{collection}.{call}({bson_to_shell(q)})")
        return ";\n".join(shells)

    elif "aggregate" in d:
        # 聚合
        collection = d["aggregate"]
        pipeline = d.get("pipeline", [])
        opt = {}
        if d.get("allowDiskUse"):
            opt["allowDiskUse"] = d["allowDiskUse"]
        opt_str = f", {bson_to_shell(opt)}" if opt else ""
        return f"db.{collection}.aggregate({bson_to_shell(pipeline)}{opt_str})"

    elif "count" in d:
        # 计数
        collection = d["count"]
        query = d.get("query", {})
        return f"db.{collection}.count({bson_to_shell(query)})"

    elif "distinct" in d:
        # 去重
        collection = d["distinct"]
        key = d.get("key")
        query = d.get("query", {})
        return f'db.{collection}.distinct("{key}", {bson_to_shell(query)})'

    elif "createIndexes" in d:
        # 索引
        collection = d["createIndexes"]
        indexes = d.get("indexes", [])
        # 只演示第一个
        if indexes:
            keys = indexes[0].get("key", {})
            name = indexes[0].get("name", "")
            return f'db.{collection}.createIndex({bson_to_shell(keys)}, {{name: "{name}"}})'
        else:
            return "createIndexes 未识别"

    # 你可以继续扩展如 drop/dropIndexes/renameCollection...
    return f"未支持命令: {d}"


# ================= MongoDB 查询监听器 =================
class MongoQueryLogger(monitoring.CommandListener):
    def __init__(self):
        self.started_commands = {}

    def started(self, event):
        col = (
            event.command.get(event.command_name)
            if isinstance(event.command, dict)
            else None
        )
        self.started_commands[event.request_id] = {
            "command_name": event.command_name,
            "command": event.command,
            "collection": col,
            "database": event.database_name,
            "start_time": time.time(),
        }

    def succeeded(self, event):
        info = self.started_commands.get(event.request_id, {})

        query_data = {
            "command": event.command_name,
            # "database": info.get("database"),
            "collection": info.get("collection", ""),
            "duration": event.duration_micros / 1000,  # 转为毫秒
            "timestamp": time.time(),
            "sql": format_mongo_shell_generic(
                pymongo_cmd_to_shell(info.get("command", {}))
            ),
            "details": bson_to_shell(info.get("command", {})),
            "path": request.path if has_request_context() else "",
        }

        # 添加到全局请求历史
        if "mongo_queries" in global_request_data:
            global_request_data["mongo_queries"].appendleft(query_data)

        # 如果没有请求上下文，直接返回
        if not has_request_context() or "_debug" not in request.args:
            return

        # 添加到单个请求
        if hasattr(g, "mongo_queries"):
            g.mongo_queries.append(query_data)


def is_flask_debug():
    # 1. 环境变量
    if os.environ.get("FLASK_DEBUG") == "1":
        return True
    # 2. Flask <=2.2 的 FLASK_ENV
    if os.environ.get("FLASK_ENV") == "development":
        return True
    # 3. 否则没法判断
    return False


def register_mongo_listener():
    if not is_flask_debug():
        return None
    """注册MongoDB查询监听器"""
    listener = MongoQueryLogger()
    monitoring.register(listener)
    return listener
