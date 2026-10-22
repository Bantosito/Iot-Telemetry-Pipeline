FROM python:3.12-slim

# Print logs straight away instead of buffering them, so `docker compose logs`
# shows readings as they happen.
ENV PYTHONUNBUFFERED=1 

WORKDIR /app

# Requirements first, code second: Docker caches each step, so editing
# main.py doesn't reinstall every dependency on the next build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py validator.py ./

# Run as an unprivileged user - if the code is ever exploited, the attacker
# isn't root inside the container.
RUN useradd --create-home --uid 10001 app
USER app

CMD ["python", "main.py"]
