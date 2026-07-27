# Sistema de Gestión de Restaurante Simplificado

Sistema liviano y eficiente diseñado para la gestión diaria de pedidos, vista en tiempo real para cocina, reportes de ventas diarias y desglose por tipo de pago.

---

## 🚀 Características Principales

- **Gestión de Pedidos (Mozo / Caja):**
  - Registro de pedidos con platos fijos y precios preconfigurados.
  - Selección del método de pago: **Efectivo**, **Yape**, o **Transferencia**.
  - Visualización del total a cobrar e ingresos ingresados según el canal de pago.

- **Vista de Cocina (KDS en Tiempo Real):**
  - Recepción automática de pedidos entrantes.
  - Botón para marcar pedido como **Listo** (notifica a la vista de pedidos).
  - Botón para **Cancelar** orden en caso de incidencias.

- **Reportes y Gráficos Sencillos:**
  - Resumen de ventas totales del día.
  - Gráficos comparativos de ingresos por método de pago (Efectivo vs Yape vs Transferencia).
  - Contador de platos más vendidos de la jornada.

---

## 🛠️ Stack Tecnológico Propuesto

- **Frontend / Backend:** Next.js (App Router) o Django.
- **Base de Datos:** Neon Postgres (Tier gratuito en Vercel) / Supabase.
- **Despliegue:** Vercel.

---

## 📋 Estado del Proyecto

- [ ] Definición de Arquitectura y Stack Final.
- [ ] Modelado de Base de Datos (Menú, Pedidos, Detalle, Pagos).
- [ ] Vista de Registro de Comandos/Pedidos.
- [ ] Vista de Pantalla de Cocina.
- [ ] Dashboard de Reportes y Gráficos.
- [ ] Despliegue en Vercel con Neon DB.
