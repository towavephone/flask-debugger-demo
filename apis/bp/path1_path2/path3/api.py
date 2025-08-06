from utils.url import get_bp
from utils.wrapper import request_wrapper, get_param
from models.task import Task

bp = get_bp(__file__, __name__)


@bp.route("/test")
@request_wrapper()
def test():
    id = get_param("id")

    if not id:
        raise Exception("id is required.")

    task = Task.find_one(
        filter={
            "_id": id,
        },
        sort=[("create_time", -1)],
        return_json=True,
    )

    return task
