# syntax = docker/dockerfile:1.4

FROM python:3.14-slim AS deploy

RUN pip3 install poetry
RUN poetry config virtualenvs.create false

WORKDIR /app

COPY poetry.lock pyproject.toml ./
RUN poetry install --no-root --no-interaction
COPY . .

ENV PYTHONPATH=/app

CMD uvicorn --factory kollie.app.main:create_app --host=0.0.0.0 --port=8080 --proxy-headers --forwarded-allow-ips=*

FROM deploy as devcontainer

RUN <<EOF
apt-get update
apt-get install -y --no-install-recommends awscli
EOF

RUN <<EOF
useradd -s /bin/bash -m vscode
groupadd docker
usermod -aG docker vscode
EOF
# install Docker tools (cli, buildx, compose)
COPY --from=gloursdocker/docker / /
