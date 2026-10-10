# Anuncios en WhatsApp Status

Los avisos de PuntoTdeA se pueden publicar como **anuncios en el Status de
WhatsApp** (historias) a traves de la **Marketing API** de Meta. No es un envio
de mensajes: es un *placement* publicitario, distinto del canal de campanas por
plantilla (`send_campaign`).

- Codigo: `communications/services/ads_service.py` (unico punto que habla con
  la Marketing API).
- Comandos: `check_meta_ads` y `create_whatsapp_status_ad`.
- Pruebas: `communications/tests/test_ads_service.py`.

## Requisitos

### Variables de entorno (`.env`)

```
META_ADS_ACCESS_TOKEN=<token de usuario con ads_management>
META_AD_ACCOUNT_ID=act_<id>
META_FB_PAGE_ID=<id de la Pagina>
META_WHATSAPP_PHONE=573332664480
META_BUSINESS_ID=<id del portafolio>   # opcional, para diagnostico
```

El token de sistema de WhatsApp **no sirve** para anuncios: hace falta un token
de usuario con `ads_management`.

### Pasos manuales en Meta (no hay API)

1. **Pagina vinculada a la cuenta de WhatsApp.** Sin esto el ad set falla con
   `code 100, subcode 2446886`.
2. **App de Meta en modo Live (publico).** En modo desarrollo, crear el creativo
   falla con `code 100, subcode 1885183`.
3. **Negocio verificado** (`verification_status: verified`) para usar un numero
   de Cloud API en anuncios.
4. **Metodo de pago** en la cuenta de anuncios (sin el, no hay entrega).
5. **Cuenta de Instagram** conectada a la Pagina (el Status exige Instagram
   Story ademas de WhatsApp Status).

## Diagnostico

```
docker compose exec -T web python manage.py check_meta_ads
```

Valida token, cuenta de anuncios, Pagina y negocio. Es de solo lectura.

## Crear un aviso

Todo se crea en **PAUSED** por defecto para probar sin gastar.

```
docker compose exec -T web python manage.py create_whatsapp_status_ad \
    --texto "Matriculas abiertas hasta el 30 de octubre" \
    --nombre "Aviso matricula" \
    --imagen media/avisos/matricula.jpg \
    --segmento 3
```

### Audiencia

- `--segmento <id>`: crea una audiencia personalizada y carga los telefonos
  suscritos del `AudienceSegment` (hash SHA-256).
- `--audiencia-id <id>`: reutiliza una audiencia ya existente.
- `--publico-amplio`: permite que Meta amplie la entrega mas alla de la lista.
  Sin este flag la entrega queda limitada a la lista (`advantage_audience=0`).

### Otros flags

- `--presupuesto <entero>`: presupuesto diario (default 2000000).
- `--pais <ISO>`: repetible; default `CO`.
- `--titulo`, `--instagram-actor-id`.
- `--campaign-id`, `--ad-set-id`: reutilizan objetos existentes.
- `--activar`: publica el anuncio (`ACTIVE`). Sin el, queda `PAUSED`.
- `--plan`: muestra el plan sin llamar a Meta.

## Referencia de errores

| code / subcode        | Significado                                             |
| --------------------- | ------------------------------------------------------- |
| 100 / 2446886         | La Pagina no esta vinculada a una cuenta de WhatsApp.   |
| 100 / 1885183         | La app de Meta esta en modo desarrollo (debe ser Live). |
| 100 / 1885204         | Bid/optimization incompatibles (usar automatico).       |

## Placement

El ad set usa el placement de Status:

```json
{
  "publisher_platforms": ["instagram", "whatsapp"],
  "instagram_positions": ["story"],
  "whatsapp_positions": ["status"],
  "user_age_unknown": false
}
```

Con `promoted_object = {"page_id": "...", "whatsapp_phone_number": "..."}`,
`optimization_goal=CONVERSATIONS`, `destination_type=WHATSAPP`,
`billing_event=IMPRESSIONS` y `bid_strategy=LOWEST_COST_WITHOUT_CAP`.
