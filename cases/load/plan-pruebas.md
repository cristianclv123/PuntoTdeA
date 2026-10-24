# Plan de pruebas de carga (k6) — módulo cases

k6 mide cuánto aguanta el servidor: peticiones por segundo, latencia y errores.
No reemplaza `manage.py test`. Esas siguen siendo las pruebas de reglas de negocio.

Alcance: solo el módulo de casos (bandeja HTML y API `/api/cases/`). El resto de módulos no entra.

Base local: `http://127.0.0.1:8000`. El servidor tiene que estar arriba antes de correr k6.

## Cómo entra k6

El login es sesión Django con CSRF. Hace falta para leer la bandeja y los tickets.

1. `GET /login/` y guardar la cookie `csrftoken`.
2. `POST /login/` con `username`, `password` y `csrfmiddlewaretoken`.
3. Reusar la cookie `sessionid` en el resto del escenario.

Usuario y contraseña van por entorno, no en el script:

```bash
k6 run -e K6_USER=asesor -e K6_PASSWORD=secret load/humo.js
```

## Tipos de prueba

| Tipo | Para qué | Cómo | Cuándo |
| --- | --- | --- | --- |
| Humo | Ver que el guion entra y las rutas de casos responden | 1 usuario virtual, ~30 s | Siempre, antes de las demás |
| Carga | Varios asesores consultando la bandeja a la vez | 10 usuarios virtuales, 2 min | Cuando el humo pasa |
| Estrés | Dónde el listado de casos empieza a fallar | Subir de 10 a 50 y luego a 100 | Después de la carga |
| Pico | Un golpe corto de consultas a la bandeja | De 5 a 40 en pocos segundos, y volver | Si la carga está estable |
| Resistencia | Si el listado se degrada con el tiempo | 10 usuarios virtuales, 15–30 min | Solo si las anteriores salen bien |

Umbral de las dos primeras: menos del 1 % de errores HTTP y el percentil 95 por debajo de 500 ms.

## Qué se prueba

Solo lectura del módulo cases, con la sesión del asesor:

- `GET /bandeja/`
- `GET /api/cases/tickets/`
- `GET /api/cases/departments/`
- `GET /api/cases/messages/?conversation={id}` sobre un ticket que ya exista

El humo hace login una vez y luego esas lecturas. La carga repite el mismo recorrido.

## Qué no se prueba con k6

Escriben el caso o disparan WhatsApp:

- `POST /api/cases/tickets/{id}/claim/`
- `POST /api/cases/tickets/{id}/reply/`
- `POST /api/cases/tickets/{id}/close/`
- `POST /bandeja/{id}/claim/`
- Webhooks `/api/cases/webhooks/` y `/api/whatsapp/webhook/`

Campañas, avisos, conocimiento y notificaciones quedan fuera de este plan.
