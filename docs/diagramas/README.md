# Diagramas de arquitectura

Fuentes `.mmd` (Mermaid) y su vista renderizada en [`index.md`](index.md). La documentación de arquitectura está en [`../arquitectura.md`](../arquitectura.md).

## Regenerar las imágenes

### Con Docker (recomendado)

```powershell
docker run --rm -v "${PWD}/docs/diagramas:/data" minlag/mermaid-cli -i 01-capas.mmd -o 01-capas.svg
```

Otros formatos: cambiá `-o 01-capas.svg` por `-o 01-capas.png` (agregá `-b white` para fondo blanco).

### Con Node (alternativa)

```powershell
npx -y @mermaid-js/mermaid-cli -i docs/diagramas/01-capas.mmd -o docs/diagramas/01-capas.svg
```

### Sin instalar nada

Pegá el contenido del `.mmd` en <https://mermaid.live> y exportá SVG/PNG/PDF.

## Reglas

- El código es la fuente de verdad: si cambia la arquitectura, actualizá el `.mmd` correspondiente.
- **No** editar el SVG/PNG a mano; editar el `.mmd` y re-renderizar.
- Los diagramas deben mantenerse alineados con `docs/arquitectura.md` y las fichas de `docs/modulos/`.
