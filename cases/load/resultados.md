# Resultados k6 — módulo cases

Fecha: 24 de octubre de 2026, 11:14–11:38 (hora local).

Cuatro de cinco pruebas cumplieron los umbrales. El estrés llegó a 100 usuarios virtuales sin errores HTTP, y el percentil 95 subió a 679 ms, por encima de los 500 ms.

## Entorno

- Servidor local: Daphne en `http://127.0.0.1:8000`, SQLite. No es Docker ni Postgres.
- k6 2.3.0. Usuario de sesión: `asesor`.
- Solo lectura: `GET /bandeja/`, `GET /api/cases/tickets/`, `GET /api/cases/departments/` y `GET /api/cases/messages/?conversation={id}`.
- Cada iteración espera 1 s entre recorridos. El login ocurre una vez, en el setup, y las VUs comparten esa sesión.
- Umbral aplicado a las cinco: menos del 1 % de errores HTTP y p95 de `http_req_duration` por debajo de 500 ms.
- Los JSON crudos quedaron en `load/out/`.

## Resumen

| Prueba | Perfil | Peticiones | RPS | Errores | p95 | Checks | Resultado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Humo | 1 VU, 30 s | 118 | 3,90 | 0 % | 17,78 ms | 117/117 | Cumple |
| Carga | 10 VU, 2 min | 4 322 | 35,77 | 0 % | 64,13 ms | 4 321/4 321 | Cumple |
| Estrés | 10 → 50 → 100, ~5 min | 33 258 | 110,67 | 0 % | 679,29 ms | 33 257/33 257 | No cumple p95 |
| Pico | 5 → 40 → 5, ~80 s | 4 386 | 54,60 | 0 % | 216,97 ms | 4 385/4 385 | Cumple |
| Resistencia | 10 VU, 15 min | 32 406 | 35,97 | 0 % | 58,41 ms | 32 405/32 405 | Cumple |

Los checks cubren el redirect del login y las cuatro lecturas (bandeja, tickets, dependencias y mensajes). Ninguno falló.

## Detalle

### Humo — cumple

11:14:45–11:15:16. 29 iteraciones.

| Métrica | Valor |
| --- | --- |
| Duración | media 10,32 ms, mediana 7,90 ms, máx 147,08 ms, p90 16,82 ms, p95 17,78 ms |
| Errores | 0 de 118 |
| Iteración | p95 1,04 s (incluye la pausa de 1 s) |

### Carga — cumple

11:15:16–11:17:17. 1 080 iteraciones, 10 VU.

| Métrica | Valor |
| --- | --- |
| Duración | media 28,13 ms, mediana 25,22 ms, máx 147,23 ms, p90 54,48 ms, p95 64,13 ms |
| Errores | 0 de 4 322 |
| Iteración | p95 1,21 s |

### Estrés — no cumple el p95

11:17:17–11:22:18. 8 314 iteraciones. Escalones: 30 s hasta 10, 1 min hasta 50, 1 min en 50, 1 min hasta 100, 1 min en 100, 30 s hasta 0.

| Métrica | Valor |
| --- | --- |
| Duración | media 260,99 ms, mediana 219,15 ms, máx 1,43 s, p90 610,42 ms, p95 679,29 ms |
| Errores | 0 de 33 258 |
| Iteración | p95 3,26 s |
| Código de salida | 99 (umbral de latencia) |

El listado siguió respondiendo 200. El límite en esta máquina aparece como latencia, no como caídas. Con SQLite y un solo proceso Daphne, 100 lecturas concurrentes de bandeja y API superan los 500 ms.

### Pico — cumple

11:22:18–11:23:38. 1 096 iteraciones. Escalones: 20 s hasta 5, 10 s hasta 40, 20 s en 40, 10 s hasta 5, 20 s en 5.

| Métrica | Valor |
| --- | --- |
| Duración | media 74,36 ms, mediana 41,87 ms, máx 316,24 ms, p90 185,27 ms, p95 216,97 ms |
| Errores | 0 de 4 386 |
| Iteración | p95 1,73 s |

El golpe de 40 usuarios virtuales se mantuvo bajo el umbral. El máximo fue 316 ms.

### Resistencia — cumple

11:23:38–11:38:40. 8 101 iteraciones, 10 VU durante 15 min.

| Métrica | Valor |
| --- | --- |
| Duración | media 27,63 ms, mediana 24,77 ms, máx 213 ms, p90 50,37 ms, p95 58,41 ms |
| Errores | 0 de 32 406 |
| Iteración | p95 1,19 s |

Quince minutos a 10 VU no degradaron el listado frente a la carga de 2 min (p95 58 ms frente a 64 ms).

## Lectura

En este servidor local, la bandeja y la API de casos aguantan 10 asesores consultando a la vez, un pico de 40 y 15 minutos seguidos, con p95 por debajo de 220 ms en el pico y de 65 ms en carga sostenida. A 100 usuarios virtuales no hubo errores, y la latencia p95 pasó de 500 ms.

Estos números son de Daphne con SQLite en una máquina de desarrollo. Un despliegue con Postgres y más de un worker puede mover ese techo. Esta corrida no escribe casos ni llama a Meta.
