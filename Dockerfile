FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

# Render no sirve los estaticos: los deja en disco y whitenoise los entrega.
# Necesita un SECRET_KEY para arrancar, aunque aqui solo se firmen manifests.
RUN DJANGO_SECRET_KEY=collectstatic-build-only \
    DJANGO_DEBUG=false \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Daphne (no runserver) porque el proyecto usa Channels/WebSocket.
# Las migraciones se ejecutan aqui: `preDeployCommand` no existe en plan free.
# El CMD se sobreescribe en render.yaml para respetar $PORT.
CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p ${PORT:-8000} PuntoTdeA.asgi:application"]