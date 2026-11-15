# Pampa Salvaje

Juego original para **Game Boy Advance**: recorrés una Argentina estilizada con tu perrito **Mate**, capturás fauna
autóctona (hornero, carpincho, ñandú, guanaco, yaguareté, zorro pampeano, pingüino de Magallanes, cóndor, vizcacha,
tero), armás un equipo de hasta 6 animales, entrás a las casas y curás a tu equipo en las veterinarias.

## Jugar

El archivo [`pampa-salvaje.gba`](pampa-salvaje.gba) es el juego completo (incluye música y gráficos).
Abrilo con cualquier emulador de GBA (por ejemplo [mGBA](https://mgba.io)).

### Controles

| Botón GBA | Tecla en mGBA | Acción |
|---|---|---|
| Flechas | Flechas | Moverse / elegir |
| B (mantener) | Z | Correr |
| A | X | Hablar / confirmar |
| START | Enter | Equipo y fauna capturada (también confirma en los menús) |
| SELECT | M* | Mapa de Argentina con las provincias |
| L | A | Ayuda |

\* En mGBA, SELECT viene en Retroceso; se puede reasignar a M en *Tools > Settings > Controllers*.

El juego todavía no tiene guardado propio (se pueden usar los estados guardados del emulador).

## Compilar

Requisitos: [devkitPro](https://devkitpro.org) con devkitARM, y [Butano](https://github.com/GValiente/butano) clonado en
`../butano` (raíz de este repositorio). Python 3 con Pillow y numpy para generar el arte.

```sh
git clone https://github.com/GValiente/butano.git ../butano   # una sola vez
python tools/gen_assets.py     # gráficos, mapa, interiores (genera graphics/ e include/)
python tools/gen_music.py      # música (genera audio/)
make -j8                       # produce pampa-salvaje.gba
```

> En Windows, `make` falla si la ruta contiene espacios: compilá desde una ruta sin espacios
> (por ejemplo con `subst G: "<carpeta del repositorio>"`).

Todo el arte, el mundo y la música se generan por código (`tools/`), así que se pueden retocar o reemplazar
por arte propio.

## Créditos

- Motor: [Butano](https://github.com/GValiente/butano) (licencia zlib).
- Límites de las provincias: [Natural Earth](https://www.naturalearthdata.com) (dominio público), en `tools/data/`.
- Arte, música y código del juego: originales.
