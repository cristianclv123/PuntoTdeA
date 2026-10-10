#!/bin/sh
# Punto de entrada del contenedor. Lo usan Render (Blueprint) y, si algun dia
# se agrega, cualquier arranque que respete el CMD del Dockerfile.
#
# En el plan free de Render NO existe `preDeployCommand` (es solo para planes
# pagos), asi que las migraciones y el superusuario inicial corren aqui, en el
# arranque. Ver docs/despliegue-render.md.
#
# `set -e` aborta si algo falla de forma definitiva: un deploy que no puede
# migrar NO debe quedar en pie sirviendo con un esquema viejo.
set -e

echo "==> Aplicando migraciones (con reintentos por si la BD aun no responde)..."

attempt=0
until python manage.py migrate --noinput; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 10 ]; then
        echo "!! No se pudo migrar tras $attempt intentos. Abortando el arranque."
        exit 1
    fi
    echo "   Intento $attempt fallido; reintentando en 3 s..."
    sleep 3
done

echo "==> Asegurando el superusuario inicial..."
# En cada redeploy este comando falla con "already taken"; el `|| echo` lo
# convierte en no-op y a proposito NO resetea la contrasena de un usuario que ya
# existe. Si faltan las variables DJANGO_SUPERUSER_*, tambien cae aqui sin
# tumbar el arranque.
python manage.py createsuperuser --noinput || echo "   superusuario ya existe, se conserva"

echo "==> Arrancando Daphne en el puerto ${PORT:-8000}..."
# `exec` reemplaza este shell por Daphne para que las senales (SIGTERM) lleguen
# directo al proceso y el apagado sea limpio.
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" PuntoTdeA.asgi:application
