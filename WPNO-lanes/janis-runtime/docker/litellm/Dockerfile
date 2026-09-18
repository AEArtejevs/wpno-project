FROM ghcr.io/berriai/litellm:main-latest@sha256:4d00db88fc8aba3e2c1cfaddbce6ae81f6de3b8826148e428ecbcc99b0a0f62b
RUN /app/.venv/bin/python3 -m ensurepip --upgrade \
    && /app/.venv/bin/python3 -m pip install --no-cache-dir psycopg2-binary
