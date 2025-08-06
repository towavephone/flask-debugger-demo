import os
from flask import Blueprint


def get_module_name(file) -> str:
    filename = os.path.basename(file).split(".")[0]
    parent = os.path.dirname(file)
    return f"{parent}/{filename}"


def get_bp(file, name, **kwargs):
    return Blueprint(get_module_name(file), name, **kwargs)
