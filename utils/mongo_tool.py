import datetime
import logging
import time
import pymongo
import os
import configparser

from utils.wrapper import get_json_result


__db = None

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "../", "config.properties"))


def db():
    global __db
    if not __db:
        db_client = pymongo.MongoClient(config["SERVER_INFO"]["DB_SERVER"])
        db_name = config["SERVER_INFO"]["DB_NAME"]
        __db = db_client[db_name]
    return __db


class MongoBase(object):
    @classmethod
    def insert_obj(cls, data):
        start_time = time.time()
        data["create_time"] = datetime.datetime.now()
        # insert data
        col_name = cls.get_collection_name()
        error = ""
        result = ""
        log_func = logging.debug
        try:
            result = db()[col_name].insert_one(data)
        except Exception as ex:
            error = ex
            log_func = logging.error
        log_func(
            "insert into %s in %.3f seconds, error is %s",
            col_name,
            time.time() - start_time,
            repr(error) if error else "",
        )
        if error:
            raise error
        return result

    @classmethod
    def distinct(cls, name, filter=None):
        col_name = cls.get_collection_name()
        return db()[col_name].distinct(name, filter=filter)

    @classmethod
    def insert(cls, **kwargs):
        # get data
        start_time = time.time()
        data = {"create_time": datetime.datetime.now()}
        for attr_name, attr_value in kwargs.items():
            if attr_name.startswith("_"):
                continue
            if type(attr_value).__name__ not in [
                "int",
                "str",
                "float",
                "list",
                "dict",
                "bool",
                "datetime",
                "Int64",
            ]:
                continue
            if attr_name == "id":
                attr_name = "_id"
            data[attr_name] = attr_value

        # insert data
        col_name = cls.get_collection_name()
        error = ""
        result = ""
        log_func = logging.debug
        try:
            result = db()[col_name].insert_one(data)
        except Exception as ex:
            error = ex
            log_func = logging.error
        log_func(
            "insert into %s in %.3f seconds, error is %s",
            col_name,
            time.time() - start_time,
            repr(error) if error else "",
        )
        if error:
            raise error
        return result

    @classmethod
    def insert_many(cls, data, ordered=True):
        start_time = time.time()
        create_time = datetime.datetime.now()
        params = []

        for kwargs in data:
            param = {"create_time": create_time}
            for attr_name, attr_value in kwargs.items():
                if attr_name.startswith("_"):
                    continue
                if type(attr_value).__name__ not in [
                    "int",
                    "str",
                    "float",
                    "list",
                    "dict",
                    "bool",
                    "datetime",
                ]:
                    continue
                if attr_name == "id":
                    attr_name = "_id"
                param[attr_name] = attr_value
            params.append(param)

        # insert data
        col_name = cls.get_collection_name()
        error = ""
        result = ""
        log_func = logging.debug
        try:
            result = db()[col_name].insert_many(params, ordered=ordered)
        except Exception as ex:
            error = ex
            log_func = logging.error
        log_func(
            "insert %d docs into %s in %.3f seconds, error is %s",
            len(data),
            col_name,
            time.time() - start_time,
            repr(error) if error else "",
        )
        if error:
            raise error
        return result

    @classmethod
    def upsert(cls, filter, update, print_log=True):
        return cls.update_one(filter, update, upsert=True, print_log=print_log)

    @classmethod
    def count(cls, filter=None):
        col_name = cls.get_collection_name()
        return db()[col_name].count(filter)

    @classmethod
    def update(
        cls,
        filter,
        update,
        skip_count=-1,
        page_size=-1,
        is_update_time=True,
        is_use_single_update=False,
    ):
        start_time = time.time()
        error = ""
        log_func = logging.debug
        result = 0
        updated = 0

        # update
        col_name = cls.get_collection_name()
        try:
            if skip_count > 0 or page_size > 0 or is_use_single_update:
                cursor = cls.find(
                    filter,
                    return_cursor=True,
                    skip_count=skip_count,
                    page_size=page_size,
                )
                result = {"nModified": 0, "nModifiedData": []}
                for item in cursor:
                    filter_param = {"_id": item["_id"]}
                    single_result = db()[col_name].update_one(filter_param, update)
                    result["nModified"] += single_result.modified_count
                    if single_result.modified_count > 0:
                        result["nModifiedData"].append(item["_id"])
                        if is_update_time:
                            db()[col_name].update_one(
                                filter_param,
                                {"$set": {"update_time": datetime.datetime.now()}},
                            )
            else:
                result = db()[col_name].update(filter, update, multi=True)
                # 下面的 update_time 并不能反映真实修改后的数据，有可能没有修改也会改到 update_time 字段
                if result["nModified"] > 0 and is_update_time:
                    db()[col_name].update(
                        filter,
                        {"$set": {"update_time": datetime.datetime.now()}},
                        multi=True,
                    )

            updated = result.get("nModified", 0)
        except Exception as ex:
            error = ex
            log_func = logging.error

        # logging
        log_func(
            "update %s in %.3f seconds, %d updated, error is %s",
            col_name,
            time.time() - start_time,
            updated,
            repr(error) if error else "",
        )
        if error:
            raise error
        return result

    @classmethod
    def update_one(
        cls, filter, update, upsert=False, is_update_time=True, print_log=True
    ):
        start_time = time.time()
        error = ""
        log_func = logging.debug
        result = 0
        updated = 0

        # update
        col_name = cls.get_collection_name()
        try:
            result = db()[col_name].update_one(filter, update, upsert=upsert)
            updated = result.modified_count
        except Exception as ex:
            error = ex
            log_func = logging.error

        if updated > 0 and is_update_time:
            update = {"$set": {"update_time": datetime.datetime.now()}}
            db()[col_name].update_one(filter, update, upsert=upsert)

        # logging
        if print_log:
            log_func(
                "update_one %s in %.3f seconds, %d updated, error is %s",
                col_name,
                time.time() - start_time,
                updated,
                repr(error) if error else "",
            )
        if error:
            raise error
        return result

    @classmethod
    def find_one(cls, filter=None, return_json=False, sort=None, fields=None):
        start_time = time.time()
        col_name = cls.get_collection_name()
        error = ""
        log_func = logging.debug
        data = None

        # query
        try:
            data = db()[col_name].find_one(
                filter, projection=fields if fields else None, sort=sort
            )
        except Exception as ex:
            error = ex
            log_func = logging.error
        log_func(
            "find one from %s in %.3f seconds (%s), error is %s",
            col_name,
            time.time() - start_time,
            "found" if data else "not found",
            repr(error) if error else "",
        )
        if error:
            raise error

        # not found
        if not data:
            return None

        if return_json:
            return get_json_result(data)

        return data

    @classmethod
    def find(
        cls,
        filter=None,
        return_cursor=False,
        fields=None,
        skip_count=-1,
        page_size=-1,
        sort=None,
        is_include_deleted=False,
        return_json=False,
    ):
        start_time = time.time()
        col_name = cls.get_collection_name()
        error = ""
        log_func = logging.debug
        count = 0
        if not filter:
            filter = {}

        # query
        try:
            if not is_include_deleted:
                filter["_deleted"] = None
            col = db()[col_name]
            if fields:
                cursor = col.find(filter, fields)
            else:
                cursor = col.find(filter)
            if sort:
                cursor = cursor.sort(sort)
            if skip_count > 0:
                cursor = cursor.skip(skip_count)
            if page_size > 0:
                cursor = cursor.limit(page_size)
            if return_cursor:
                count = cursor.count()
                return cursor
            else:
                data = [it for it in cursor]

                if return_json:
                    data = get_json_result(data)

                count = len(data)
                return data
        except Exception as ex:
            error = ex
            log_func = logging.error
        finally:
            log_func(
                "find from %s in %.3f seconds, count is %d, error is %s",
                col_name,
                time.time() - start_time,
                count,
                repr(error) if error else "",
            )
            if error:
                raise error

    @classmethod
    def delete(cls, filter=None, real_delete=False, multi=False):
        start_time = time.time()
        col_name = cls.get_collection_name()
        error = ""
        log_func = logging.debug

        if not filter:
            filter = {}

        # query
        try:
            if "id" in filter:
                filter["_id"] = filter["id"]
                del filter["id"]
            if not real_delete:
                if multi:
                    db()[col_name].update(filter, {"$set": {"_deleted": 1}}, multi=True)
                else:
                    db()[col_name].update_one(filter, {"$set": {"_deleted": 1}})
            else:
                db()[col_name].remove(filter, multi=multi)
        except Exception as ex:
            error = ex
            log_func = logging.error
        finally:
            log_func(
                "delete from %s in %.3f seconds, error is %s",
                col_name,
                time.time() - start_time,
                repr(error) if error else "",
            )
            if error:
                raise error

    @classmethod
    def get_collection_name(cls):
        if hasattr(cls, "__collection__") and cls.__collection__:
            return cls.__collection__

        result = ""
        for ch in cls.__name__:
            if result and "A" <= ch <= "Z":
                result += "_" + ch.lower()
            else:
                result += ch.lower()
        return result + "s"

    @classmethod
    def get_collection(cls):
        return db()[cls.get_collection_name()]

    @classmethod
    def get_auto_increasing_id(cls):
        col = db()["ids"]
        where = {"name": cls.get_collection_name()}
        update = {"$inc": {"id": 1}}
        item = col.find_one_and_update(
            where, update, upsert=True, return_document=pymongo.ReturnDocument.AFTER
        )
        return item["id"]

    @classmethod
    def set_auto_increasing_id(cls, id):
        col = db()["ids"]
        where = {"name": cls.get_collection_name()}
        update = {"$set": {"id": id}}
        item = col.find_one_and_update(
            where, update, upsert=True, return_document=pymongo.ReturnDocument.AFTER
        )
        return item["id"]

    @classmethod
    def aggregate(cls, match=None, return_cursor=False, allowDiskUse=False):
        start_time = time.time()
        col_name = cls.get_collection_name()
        error = ""
        log_func = logging.debug
        cursor = None
        count = 0
        if not match:
            match = []

        # query
        try:
            cursor = db()[col_name].aggregate(match, allowDiskUse=allowDiskUse)
            if return_cursor:
                return cursor
            else:
                data = [it for it in cursor]
                count = len(data)
                return data
        except Exception as ex:
            error = ex
            log_func = logging.error
        finally:
            log_func(
                "aggregate from %s in %.3f seconds, count is %d, error is %s",
                col_name,
                time.time() - start_time,
                count,
                repr(error) if error else "",
            )
            if error:
                raise error
