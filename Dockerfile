FROM python:3.9.16-alpine as builder

WORKDIR /app
COPY . .

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    apk add --no-cache --upgrade gcc musl-dev python3-dev libffi-dev openssl-dev build-base && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /data/python_wheels -r requirements.txt

FROM python:3.9.16-alpine

LABEL maintainer="hoshinosuzumi"
LABEL org.opencontainers.image.source=https://github.com/UniiemStudio/CTFever-Premium-Service

WORKDIR /app
COPY . .

ENV ENVIRONMENT production

COPY --from=builder /data/python_wheels /data/python_wheels

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    apk add --no-cache unzip p7zip && \
    pip install --no-cache /data/python_wheels/* && \
    rm -rf /data/python_wheels

EXPOSE 9563

VOLUME /app/data
VOLUME /app/log

CMD ["python", "main.py"]
