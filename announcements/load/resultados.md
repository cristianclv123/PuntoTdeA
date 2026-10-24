# Resultados k6 — módulo announcements

Fecha: 24 de octubre de 2026, 12:41–13:05 (hora local).

Las cinco pruebas cumplieron los umbrales: 0 % de errores HTTP y p95 por debajo de 39 ms, también con 100 usuarios virtuales.

## Entorno

- Servidor local: Daphne en `http://127.0.0.1:8000`, SQLite. No es Docker ni Postgres.
- k6. Usuario de sesión: `asesor`.
- Solo lectura: `GET /avisos/`. La página no tenía avisos con imagen, así que `GET /avisos/imagen/{id}/` no se ejecutó.
- Cada iteración espera 1 s entre lecturas. El login ocurre una vez, en el setup, y las VUs comparten esa sesión.
- Umbral: menos del 1 % de errores HTTP y p95 de `http_req_duration` por debajo de 500 ms.
- Los JSON crudos quedaron en `announcements/load/out/`.

## Resumen

| Prueba | Perfil | Peticiones | RPS | Errores | p95 | Checks | Resultado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Humo | 1 VU, 30 s | 32 | 1,04 | 0 % | 20,37 ms | 31/31 | Cumple |
| Carga | 10 VU, 2 min | 1 183 | 9,77 | 0 % | 38,26 ms | 1 182/1 182 | Cumple |
| Estrés | 10 → 50 → 100, ~5 min | 16 663 | 55,37 | 0 % | 38,99 ms | 16 662/16 662 | Cumple |
| Pico | 5 → 40 → 5, ~80 s | 1 401 | 17,29 | 0 % | 28,19 ms | 1 400/1 400 | Cumple |
| Resistencia | 10 VU, 15 min | 8 815 | 9,78 | 0 % | 32,63 ms | 8 814/8 814 | Cumple |

Los checks cubren el redirect del login y `GET /avisos/` en 200. Ninguno falló.

## Detalle

### Humo — cumple

12:41:50–12:42:22. 30 iteraciones.

| Métrica | Valor |
| --- | --- |
| Duración | media 17,82 ms, mediana 13,02 ms, máx 161,35 ms, p90 17,52 ms, p95 20,37 ms |
| Errores | 0 de 32 |

### Carga — cumple

12:42:22–12:44:23. 1 181 iteraciones, 10 VU.

| Métrica | Valor |
| --- | --- |
| Duración | media 21 ms, mediana 19,54 ms, máx 150,65 ms, p90 33,53 ms, p95 38,26 ms |
| Errores | 0 de 1 183 |

### Estrés — cumple

12:44:23–12:49:25. 16 661 iteraciones. Escalones: 30 s hasta 10, 1 min hasta 50, 1 min en 50, 1 min hasta 100, 1 min en 100, 30 s hasta 0.

| Métrica | Valor |
| --- | --- |
| Duración | media 16,48 ms, mediana 13,07 ms, máx 249,27 ms, p90 26,72 ms, p95 38,99 ms |
| Errores | 0 de 16 663 |

A 100 usuarios virtuales la página de avisos siguió por debajo de 500 ms. El máximo fue 249 ms.

### Pico — cumple

12:49:25–12:50:46. 1 399 iteraciones. Escalones: 20 s hasta 5, 10 s hasta 40, 20 s en 40, 10 s hasta 5, 20 s en 5.

| Métrica | Valor |
| --- | --- |
| Duración | media 12,26 ms, mediana 9,15 ms, máx 149,95 ms, p90 23,73 ms, p95 28,19 ms |
| Errores | 0 de 1 401 |

### Resistencia — cumple

12:50:46–13:05:48. 8 813 iteraciones, 10 VU durante 15 min.

| Métrica | Valor |
| --- | --- |
| Duración | media 20,35 ms, mediana 19,34 ms, máx 153,96 ms, p90 30,03 ms, p95 32,63 ms |
| Errores | 0 de 8 815 |

Quince minutos a 10 VU no degradaron el listado frente a la carga de 2 min (p95 33 ms frente a 38 ms).

## Lectura

En este servidor local, listar avisos aguanta 10 asesores, un pico de 40, 15 minutos seguidos y 100 usuarios virtuales, con p95 por debajo de 40 ms. La página es una sola lectura HTML. Esta corrida no midió la imagen ni escribió avisos, y no llamó a WhatsApp Status.
