# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE COPYRIGHT ./
COPY alfdockia ./alfdockia
RUN pip install --no-cache-dir .

EXPOSE 8083

CMD ["sh", "-c", "exec uvicorn alfdockia.community.search.ia.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8083}"]
