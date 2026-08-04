# Contexto: Catálogo y Menú del Restaurante

> **Propósito de este documento**: fuente de la verdad de los requisitos de catálogo y precios.
> Antes de implementar ningún cambio, este documento debe estar en línea con la realidad de negocio.
> Todo lo marcado como **[PENDIENTE]** debe resolverse con el dueño antes del diseño.

---

## 1. Concepto de "Menú"

**El "Menú" es un combo sellado**: engloba **una entrada + un segundo**.

- El cliente pide "menú" y elige una sopa de la categoría Entrada + un plato de la categoría Segundo.
- El menú tiene **UN precio fijo £(independiente de qué sopa y qué segundo elija)**, más barato que comprar entrada + segundo a la carta.
  - A la carta: sopa 6 + segundo 11 = 17 S/.
  - **Menú: precio fijo [PENDIENTE: definir, p.ej. 12 S/].**
- **"Menú 13" queda descartado.** El nombre es simplemente **"Menú"**.

> Estructura de negocio: `Menu (entrada + segundo, precio fijo)` → el cliente elige dentro de las categorías incluidas.

> **CONFIRMADO:** cualquier sopa de Entradas + cualquier plato de Segundos entran en el Menú (sin restricción). El `Menu` se arma con las categorías completas.

> **CONFIRMADO:** el precio del Menú es **13 S/ actualmente**, pero es **configurable/editable** (cambio en la base/admin, ejemplo cambiar a 15 sin tocar código). No hardcodear.

---

## 2. Categorías del catálogo

El negocio maneja **tres cortes de carta**:

| Categoría      | Rol |
|----------------|-----|
| **Entrada**    | Sopas / caldos |
| **Segundo**    | Platos principales |
| **Añadidos**   | Extras cobrables (porción arroz, papas, huevo) |

> **Requisito de negocio (modificabilidad):** la lista de categorías, platos y añadidos debe poder **agregarse, editarse y eliminarse** sin tocar código. El catálogo vive en base de datos (editable desde admin), y se mantiene una **semilla/archivo** para repoblarlo desde cero cuando se quiera volver al estado inicial.

---

## 3. Catálogo inicial (semilla)

### 3.1 Entradas (precio base)

| Plato            | Precio |
|------------------|--------|
| Sopa de Res      | 6.00 S/ |

### 3.2 Segundos (precio base 11 S/ cada uno)

- Lomo Saltado
- Pollo Dorado
- Hamburguesa al Plato
- Chuleta de Res
- Saltado de Mollejas
- Hígado Frito
- Pollo Broaster
- Riñón Saltado
- Chuleta de Chancho
- Arroz a la Cubana

### 3.3 Añadidos

| Añadido         | Precio |
|-----------------|--------|
| Huevo           | 1.50 S/ |
| Porción de Arroz| 3.00 S/ |
| Porción de Papa | 3.00 S/ |

> **PENDIENTE:** ¿todos los segundos valen exactamente 11 S/, o hay alguno distinto?
> **PENDIENTE:** ¿"Sopa de Res" es la única entrada, o querés poder meter más entradas después?
> **PENDIENTE:** ¿un segundo incluye arroz/papa de base, o TODO arroz/papa va como añadido?

---

## 4. Regla de precios "para llevar"

El precio final depende de cuántos tapers lleve el pedido. **Cada plato "empaquétable" = 1 taper.** Solo cuentan la **sopa y el segundo** (no los añadidos).

- **Solo sopa para llevar** → 1 taper → **+1 S/**.
- **Solo segundo para llevar** → 1 taper → **+1 S/**.
- **Sopa + segundo para llevar** → 2 tapers → **+2 S/**.
- **Añadidos**: NO afectan tapers; solo suman su precio al total.
- **Aplica solo a "Para Llevar" (LLEVAR)**, no a mesa.

**Recargo configurable:** el monto por taper es **1 S/ hoy** pero debe ser **configurable/editable** (campo en admin), no hardcodeado. Cálculo: `total = platos + añadidos + (nº_de_tapers) × (recargo_por_taper)`.

> **CONFIRMADO con el dueño (2026-08-03).**
> 
> | Caso para llevar | Tapers | Recargo |
> |---|---|---|
> | Solo sopa | 1 | +1 |
> | Solo segundo | 1 | +1 |
> | Sopa + segundo | 2 | +2 |
> | Añadido (no empaque) | 0 | solo suma al total |

---

## 5. Modelo de datos objetivo (borrador)

```
Categoria (Entrada | Segundo | Añadidos)
   └── Plato
         nombre, precio, activo

Menu                       <- NUEVO: combo "entrada + segundo", precio fijo
   ├── nombre              <- "Menú"
   ├── precio              <- precio fijo sellado (barato)
   ├── categorias incluidas<- p.ej. Entrada + Segundo (catálogos elegibles)
   └── activo

Orden
   └── DetalleOrden
         plato, cantidad, precio_unitario, nota
         + (¿tipo: a la carta o menú?)
```

> Este modelo requiere **migración** (nueva tabla `Menu` + ajuste de `DetalleOrden` si el menú se cobra como unidad). Validar antes de implementar.

---

## 6. Reglas transversales (a validar)

1. **Modificabilidad total:** todo el catálogo editable desde admin. La semilla solo restablece el estado inicial.
2. **Recargos configurables:** el monto de "para llevar" por taper es configurable.
3. **Sin pedir más modelos de los necesarios:** reutilizar `Categoria` + `Plato` salvo que haga falta el combo.

---

## 7. Preguntas abiertas

- [ ] Qué es exactamente "Menú 13" (nombre vs combo vs precio).
- [ ] Segundos: todos a 11 S/ o precios individuales.
- [ ] Sopa: ¿solo Sopa de Res o más entradas?
- [ ] ¿El plato base incluye arroz/papa o todo es añadido?
- [ ] Para llevar: reglas exactas (monto, tapers, nuevo papa sólo, añadidos).
- [ ] ¿El recargo "para llevar" es configurable en admin?

---

*Última edición: 2026-08-03. Documento de contexto, no especificación final.*