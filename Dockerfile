FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

# El entrypoint debe viajar con saltos de linea LF: en Windows git puede dejarlo
# en CRLF y dentro del contenedor el shell falla con "not found" por el \r.
# Normalizamos y le damos permiso de ejecucion.
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Render no sirve los estaticos: los deja en disco y whitenoise los entrega.
# Necesita un SECRET_KEY para arrancar, aunque aqui solo se firmen manifests.
RUN DJANGO_SECRET_KEY=collectstatic-build-only \
    DJANGO_DEBUG=false \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Daphne (no runserver) porque el proyecto usa Channels/WebSocket.
# El arranque completo (migraciones + superusuario + Daphne) vive en
# entrypoint.sh, porque en el plan free de Render no existe `preDeployCommand`
# (es solo para planes pagos). Ver docs/despliegue-render.md.
#
# NO lo sobreescribas con `dockerCommand`: ni en `render.yaml` ni en el panel de
# Render (Settings -> Docker Command). Render pasa ese valor como una sola cadena
# y anidar `/bin/bash -c "..."` ahi rompe el escapado de comillas (sale con 127).
# Deja "Docker Command" VACIO en el panel para que Render use este CMD.
#
# El superusuario se crea en el arranque: el plan free no da Shell y la Postgres
# free no expone URL externa, asi que el arranque es el UNICO momento en que
# corre codigo en Render. `createsuperuser --noinput` lee DJANGO_SUPERUSER_* y
# nunca muestra la contrasena. A proposito NO resetea la de un usuario existente.
CMD ["sh", "/app/entrypoint.sh"]