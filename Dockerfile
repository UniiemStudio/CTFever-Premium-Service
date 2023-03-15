FROM python:3.9.16-alpine as builder
WORKDIR /app
COPY . .

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk add --update gcc musl-dev python3-dev libffi-dev openssl-dev build-base && pip install --upgrade pip && pip wheel --no-cache-dir --no-deps --wheel-dir /data/python_wheels -r requirements.txt

FROM python:3.9.16-alpine
LABEL maintainer="hoshinosuzumi"
WORKDIR /app
COPY . .

ENV ENVIRONMENT production

COPY --from=builder /data/python_wheels /data/python_wheels
RUN pip install --no-cache /data/python_wheels/* && apk add unzip p7zip

EXPOSE 9563

VOLUME /app/data
VOLUME /app/log

CMD ["python", "main.py"]
