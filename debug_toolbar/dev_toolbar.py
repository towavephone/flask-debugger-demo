import flask_debugtoolbar
from flask import request, make_response, render_template_string, g
import time
from collections import deque

# 所有历史累积数据
global_request_data = {"mongo_queries": deque(maxlen=200)}


class DevToolbar:
    """Add debug toolbars with json to html

    Note you must pass `_debug` param to convert the json response
    """

    def __init__(self, app):
        wrap_json = """
        <html>
            <head>
                <title>Flask Debug Toolbar</title>
            </head>

            <body>
                <h2>HTTP Code</h2>
                <pre>{{ http_code }}</pre>

                <h2>JSON Response</h2>
                <pre>{{ response }}</pre>
            </body>
        </html>
        """

        @app.before_request
        def before_request():
            if "_debug" not in request.args:
                return

            # print(f"Init Request: {request.path}")

            g.start_time = time.time()
            g.mongo_queries = deque(maxlen=50)

        @app.after_request
        def after_request(response):
            if response.mimetype == "application/json" and (
                request.full_path == "/?" or "_debug" in request.args
            ):
                html_wrapped_response = make_response(
                    render_template_string(
                        wrap_json,
                        response=response.data.decode("utf-8"),
                        http_code=response.status,
                    ),
                    response.status_code,
                )
                return app.process_response(html_wrapped_response)

            return response

        flask_debugtoolbar.DebugToolbarExtension(app)
