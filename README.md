# EURO - Sistema de Gestión de Terceros

Backend desarrollado con Django REST Framework para el sistema de gestión de terceros de EURO.

## 📋 Descripción

Sistema integral para la gestión de terceros (personas naturales y jurídicas) con workflows de aprobación, validación de documentos y verificación contra listas restrictivas internacionales.

## 🚀 Características Principales

### 🔐 Autenticación y Roles
- **JWT Authentication** con refresh tokens
- **Tres roles de usuario**:
  - **Comercial**: Creación de terceros
  - **Procesos**: Aprobación y revisión 
  - **Gestión Humana**: Aprobación y gestión completa

### 👥 Gestión de Terceros
- Registro de personas naturales y jurídicas
- Workflow de aprobación multinivel
- Historial completo de cambios de estado
- Validación de datos y documentos de identidad

### 📁 Gestión de Documentos
- Upload de documentos con validación de tipos
- Estados de validación (Pendiente, Aprobado, Rechazado)
- Soporte para PDF, imágenes y documentos Office
- Historial de cambios en documentos

### 🔍 Validaciones de Listas Restrictivas
- Validación automática contra múltiples listas:
  - OFAC (Office of Foreign Assets Control)
  - Lista de Sanciones ONU
  - Lista Clinton
  - Listas locales (Contraloría, Procuraduría)
- Sistema de coincidencias con niveles de similitud
- Manejo de falsos positivos
- Alertas automáticas

### 📊 Dashboard y Métricas
- Dashboard personalizable por rol
- Métricas en tiempo real
- Alertas y notificaciones
- Configuración personalizada por usuario

## 🛠️ Tecnologías

- **Backend**: Django 4.2.7
- **API**: Django REST Framework 3.14.0
- **Autenticación**: djangorestframework-simplejwt 5.3.0
- **Base de Datos**: SQLite (desarrollo) / PostgreSQL (producción)
- **CORS**: django-cors-headers 4.3.1
- **Filtros**: django-filter 23.4
- **Variables de Entorno**: python-decouple 3.8
- **Imágenes**: Pillow 10.1.0

## 📦 Instalación

### Prerrequisitos
- Python 3.11+
- pip
- Git

### Pasos de Instalación

1. **Clonar el repositorio**
```bash
git clone <url-del-repositorio>
cd euro_backend
```

2. **Crear entorno virtual**
```bash
python -m venv venv
```

3. **Activar entorno virtual**
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

5. **Configurar variables de entorno**
```bash
# Copiar y editar archivo .env
cp .env.example .env
```

6. **Ejecutar migraciones**
```bash
python manage.py migrate
```

7. **Crear superusuario**
```bash
python manage.py createsuperuser
```

8. **Ejecutar servidor de desarrollo**
```bash
python manage.py runserver
```

## ⚙️ Configuración

### Variables de Entorno (.env)

```env
# Django Configuration
SECRET_KEY=tu-clave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DATABASE_URL=sqlite:///db.sqlite3

# Email Configuration (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tu_email@gmail.com
EMAIL_HOST_PASSWORD=tu_password

# File Upload Settings
MAX_UPLOAD_SIZE=5242880
```

## 🏗️ Arquitectura del Proyecto

```
euro_backend/
├── accounts/           # Gestión de usuarios y autenticación
├── terceros/          # Gestión principal de terceros
├── documents/         # Gestión de documentos
├── validations/       # Validaciones contra listas restrictivas
├── dashboard/         # Métricas y dashboard
├── euro_terceros/     # Configuración principal
├── media/            # Archivos subidos
├── logs/             # Logs del sistema
└── requirements.txt  # Dependencias
```

## 📚 API Endpoints

### Autenticación
```
POST /api/auth/login/     # Iniciar sesión
POST /api/auth/refresh/   # Renovar token
POST /api/auth/verify/    # Verificar token
```

### Usuarios
```
GET  /api/accounts/profile/          # Perfil del usuario
GET  /api/accounts/users/            # Lista de usuarios
```

### Terceros
```
GET    /api/terceros/terceros/                    # Lista de terceros
POST   /api/terceros/terceros/                    # Crear tercero
GET    /api/terceros/terceros/{id}/               # Detalle tercero
PUT    /api/terceros/terceros/{id}/               # Actualizar tercero
PATCH  /api/terceros/terceros/{id}/approve/       # Aprobar tercero
PATCH  /api/terceros/terceros/{id}/reject/        # Rechazar tercero
GET    /api/terceros/terceros/{id}/historial/     # Historial tercero
```

### Documentos
```
GET    /api/documents/tipos-documento/            # Tipos de documento
GET    /api/documents/documentos/                 # Lista documentos
POST   /api/documents/documentos/                 # Subir documento
PATCH  /api/documents/documentos/{id}/validate/   # Validar documento
GET    /api/documents/terceros/{id}/documentos/   # Docs de tercero
```

### Validaciones
```
GET    /api/validations/listas-restrictivas/      # Listas restrictivas
GET    /api/validations/validaciones/             # Validaciones
POST   /api/validations/terceros/{id}/validate/   # Validar tercero
PATCH  /api/validations/coincidencias/{id}/mark-false-positive/
```

### Dashboard
```
GET    /api/dashboard/overview/         # Resumen dashboard
GET    /api/dashboard/metricas/         # Métricas
GET    /api/dashboard/alertas/          # Alertas
POST   /api/dashboard/metricas/calculate/
```

## 👥 Roles y Permisos

### Comercial
- ✅ Crear terceros
- ✅ Ver terceros propios
- ✅ Subir documentos
- ❌ Aprobar terceros
- ❌ Acceso completo dashboard

### Procesos
- ✅ Ver todos los terceros
- ✅ Aprobar/rechazar terceros
- ✅ Validar documentos
- ✅ Dashboard completo
- ❌ Crear terceros

### Gestión Humana
- ✅ Todas las funciones
- ✅ Gestión de usuarios
- ✅ Configuración del sistema
- ✅ Dashboard administrativo

## 🔧 Desarrollo

### Estructura de Apps

#### accounts/
- `models.py`: Modelo User personalizado con roles
- `views.py`: Vistas de autenticación y perfil
- `admin.py`: Panel admin para usuarios

#### terceros/
- `models.py`: Modelo Tercero y HistorialAprobacion
- `views.py`: CRUD y workflow de aprobación
- `admin.py`: Gestión administrativa

#### documents/
- `models.py`: TipoDocumento, DocumentoTercero, HistorialDocumento
- `views.py`: Upload y validación de documentos
- `admin.py`: Gestión de documentos

#### validations/
- `models.py`: ListaRestrictiva, ValidacionTercero, CoincidenciaLista
- `views.py`: Validaciones automáticas
- `admin.py`: Configuración de validaciones

#### dashboard/
- `models.py`: MetricaTerceros, AlertaDashboard, ConfiguracionDashboard
- `views.py`: Métricas y alertas
- `admin.py`: Configuración dashboard

### Comandos Útiles

```bash
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Ejecutar tests
python manage.py test

# Recopilar archivos estáticos
python manage.py collectstatic

# Shell de Django
python manage.py shell
```

## 📝 Logs

Los logs se almacenan en:
- `logs/euro_terceros.log` - Log principal del sistema
- Console - Logs de desarrollo

## 🔒 Seguridad

- Autenticación JWT con refresh tokens
- Validación de permisos por rol
- Sanitización de archivos subidos
- Validación de entrada de datos
- CORS configurado para frontend
- Variables de entorno para datos sensibles

## 🌐 Frontend Integration

El backend está preparado para integrarse con un frontend React:
- CORS configurado para desarrollo (localhost:3000, localhost:8080)
- Autenticación JWT estándar
- Responses JSON consistentes
- Paginación incluida

## 📱 Panel de Administración

Accede al panel admin en: `http://localhost:8000/admin/`

Usuarios por defecto:
- **Username**: admin
- **Email**: admin@euro.com
- **Password**: [password configurado]

## 🚀 Despliegue en Producción

### Variables de Entorno Producción
```env
DEBUG=False
SECRET_KEY=clave-super-secreta-produccion
DATABASE_URL=postgresql://user:pass@host:5432/euro_db
ALLOWED_HOSTS=tu-dominio.com
```

### Pasos para Producción
1. Configurar base de datos PostgreSQL
2. Configurar servidor web (Nginx/Apache)
3. Usar Gunicorn como WSGI server
4. Configurar SSL/HTTPS
5. Configurar respaldos automáticos

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crea un Pull Request

## 📄 Licencia

Este proyecto es privado y confidencial de EURO.

## 📞 Contacto

Para soporte técnico o consultas sobre el sistema, contacta al equipo de desarrollo.

---

**EURO - Sistema de Gestión de Terceros** | Versión 1.0.0 | Django 4.2.7
