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
#
# Este CMD es la unica fuente de verdad del arranque. NO lo sobreescribas con
# `dockerCommand` en render.yaml: Render pasa ese valor como una sola cadena y
# anidar `/bin/bash -c "..."` ahi rompe el escapado de comillas (sale con 127).
# `${PORT:-8000}` lo resuelve el propio shell, asi que ya respeta el PORT de
# Render sin necessidade de configuracion extra.
# El superusuario tambien se crea aqui. El plan free no da Shell y la Postgres
# free no expone URL externa, asi que el arranque del contenedor es el UNICO
# momento en que corre codigo en Render: si no va en este CMD, no hay forma de
# crear el usuario. `createsuperuser --noinput` lee el usuario del entorno
# (DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD) y nunca muestra la contrasena.
#
# El `( ... || echo ... )` es obligatorio: en cada redeploy el comando falla con
# "That username is already taken", y sin ese parentesis tumbaba el deploy
# entero. A proposito NO resetea la contrasena de un usuario ya existente.
CMD ["sh", "-c", "python manage.py migrate --noinput && (python manage.py createsuperuser --noinput || echo 'superusuario ya existe, se conserva') && daphne -b 0.0.0.0 -p ${PORT:-8000} PuntoTdeA.asgi:application"]