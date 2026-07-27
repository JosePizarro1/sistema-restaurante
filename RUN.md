# 🚀 Guía de Ejecución Local - Sistema Restaurante

Esta guía contiene los comandos exactos paso a paso para levantar y probar la aplicación en tu entorno local.

---

## 1. Clonar el Repositorio (si estás en otra PC)

```bash
git clone https://github.com/JosePizarro1/sistema-restaurante.git
cd sistema-restaurante
```

---

## 2. Crear y Activar Entorno Virtual

### En Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### En Linux / Mac:
```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

---

## 4. Ejecutar Migraciones y Cargar Datos Iniciales

Ejecuta las migraciones de la base de datos local y el comando para cargar el usuario admin y los platos iniciales de demostración:

```bash
python manage.py migrate
python manage.py poblar_datos
```

---

## 5. Iniciar el Servidor Local

```bash
python manage.py runserver
```

El servidor iniciará en: **`http://127.0.0.1:8000/`**

---

## 🔑 Credenciales por Defecto

- **Usuario:** `admin`
- **Contraseña:** `admin123`

---

## 📌 Rutas Disponibles

- 🔐 **Login:** `http://127.0.0.1:8000/login/`
- 🛒 **Punto de Venta / Mozo (POS):** `http://127.0.0.1:8000/`
- 👨‍🍳 **Pantalla de Cocina:** `http://127.0.0.1:8000/cocina/`
- 📊 **Reportes y Gráficos:** `http://127.0.0.1:8000/reportes/`
- ⚙️ **Panel de Administración (Agregar/Editar Platos):** `http://127.0.0.1:8000/admin/`
