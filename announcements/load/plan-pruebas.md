# Plan de pruebas de carga (k6) — módulo announcements

k6 mide cuánto aguanta el servidor: peticiones por segundo, latencia y errores.
No reemplaza `manage.py test`. Esas siguen siendo las pruebas de reglas de negocio.

Alcance: solo el módulo de avisos (`/avisos/`). El resto de módulos no entra.

Base local: `http://127.0.0.1:8000`. El servidor tiene que estar arriba antes de correr k6.

## Cómo entra k6

El login es sesión Django con CSRF. Hace falta para leer la página de avisos.

1. `GET /login/` y guardar la cookie `csrftoken`.
2. `POST /login/` con `username`, `password` y `csrfmiddlewaretoken`.
3. Reusar la cookie `sessionid` en el resto del escenario.

Usuario y contraseña van por entorno, no en el script. Desde la raíz del proyecto:

```bash
k6 run -e K6_USER=asesor -e K6_PASSWORD=secret announcements/load/humo.js
```

## Tipos de prueba

| Tipo | Para qué | Cómo | Cuándo |
| --- | --- | --- | --- |
| Humo | Ver que el guion entra y las rutas de avisos responden | 1 usuario virtual, ~30 s | Siempre, antes de las demás |
| Carga | Varios asesores consultando los avisos a la vez | 10 usuarios virtuales, 2 min | Cuando el humo pasa |
| Estrés | Dónde el listado de avisos empieza a fallar | Subir de 10 a 50 y luego a 100 | Después de la carga |
| Pico | Un golpe corto de consultas a los avisos | De 5 a 40 en pocos segundos, y volver | Si la carga está estable |
| Resistencia | Si el listado se degrada con el tiempo | 10 usuarios virtuales, 15 min | Solo si las anteriores salen bien |

Umbral: menos del 1 % de errores HTTP y el percentil 95 por debajo de 500 ms.

## Qué se prueba

Solo lectura del módulo announcements, con la sesión del asesor:

- `GET /avisos/`
- `GET /avisos/imagen/{id}/` si la página ya muestra un aviso con imagen

El humo hace login una vez y luego esas lecturas. La carga, el estrés, el pico y la resistencia repiten el mismo recorrido.

## Qué no se prueba con k6

Escriben el aviso o disparan WhatsApp Status:

- `POST /avisos/` con acción `create`
- `POST /avisos/` con acción `publish_status_create`
- `POST /avisos/` con acción `publish_status`
- `POST /avisos/` con acción `delete`

Campañas, casos, conocimiento y notificaciones quedan fuera de este plan.
