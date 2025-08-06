FROM python:3.7

ARG PIP_SOURCE=https://mirrors.aliyun.com/pypi/simple

COPY requirements.txt /

RUN pip3 install -r /requirements.txt -i ${PIP_SOURCE}

COPY . /app/

ENV PYTHONPATH /app

WORKDIR /app

EXPOSE 5000
