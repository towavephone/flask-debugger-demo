#!/bin/bash
top_dir=$(pwd)
echo $top_dir

entry='flask run --host 0.0.0.0 --port=3004'
log_file_url='/var/log/flask-debugger-demo'
FLASK_DEBUG=true

if [ "$1" = '-b' ]; then
  entry='/bin/bash'
elif [ "$1" = '-p' ]; then
  entry="gunicorn app:app --bind 0.0.0.0:3004 --reload --log-file=$log_file_url/gunicorn.log"
  FLASK_DEBUG=false
fi

docker run -it --rm \
    -p 3004:3004 \
    -p 6534:6534 \
    --env=FLASK_APP=app.py \
    --env=FLASK_DEBUG=$FLASK_DEBUG \
    --env=TZ=Asia/Shanghai \
    -v $top_dir:/app \
    -v $log_file_url:$log_file_url \
    flask-debugger-demo $entry
