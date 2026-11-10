FROM python:3.11.9-alpine AS build

WORKDIR /app

# Build deps for pip packages that need compilation
RUN apk add --no-cache --virtual .build-deps gcc musl-dev

# Install python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir \
    -r requirements.txt

# Install rclone (runtime binary)
RUN apk add --no-cache rclone


FROM python:3.11.9-alpine AS runtime

WORKDIR /app

# TZ=Asia/Shanghai (see docker-compose) needs the zoneinfo database.
RUN apk add --no-cache tzdata

# Copy installed deps from build stage
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy rclone to the path expected by the app (matches code default: ./rclone/rclone)
COPY --from=build /usr/bin/rclone /app/rclone/rclone

# Copy app source code
COPY . /app

CMD ["python", "media_downloader.py"]
