# 🚌 Buscador de Buses Colombia

API REST para buscar horarios de buses en Colombia con sistema de alertas de disponibilidad en tiempo real.

## 🌟 Características

- ✅ Búsqueda de horarios en **todas las empresas** de buses de Colombia
- ✅ Soporte para **todas las ciudades** sin mapeo hardcodeado
- ✅ Sistema de **monitoreo** y **alertas** automáticas
- ✅ Notificaciones cuando quedan pocos asientos disponibles
- ✅ API REST completa y documentada

## 🚀 Empresas Soportadas

A través de redBus, la API tiene acceso a:
- Expreso Brasilia
- Rápido Ochoa
- Copetran
- Berlinas del Fonce
- Concorde
- Y muchas más...

## 📋 Requisitos

- Python 3.8+
- pip

## 🔧 Instalación

1. **Clonar el repositorio:**
```bash
git clone https://github.com/tu-usuario/buscador-buses-colombia.git
cd buscador-buses-colombia
```

2. **Crear entorno virtual (recomendado):**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

## ▶️ Ejecutar
```bash
python main.py
```

El servidor estará disponible en: `http://localhost:8000`

## 📚 Documentación

Accede a la documentación interactiva en:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🎯 Ejemplos de Uso

### 1. Buscar horarios entre ciudades
```bash
GET http://localhost:8000/buscar?origen=barranquilla&destino=medellin&fecha=2025-11-22
```

### 2. Filtrar por empresa
```bash
GET http://localhost:8000/buscar?origen=bogota&destino=cali&fecha=2025-12-01&empresa=brasilia
```

### 3. Buscar ciudad
```bash
GET http://localhost:8000/buscar-ciudad?ciudad=cartagena
```

### 4. Monitorear una ruta
```bash
POST http://localhost:8000/monitorear?origen=barranquilla&destino=medellin&fecha=2025-11-22&horario=19:00&empresa=ochoa
```

### 5. Ver alertas generadas
```bash
GET http://localhost:8000/alertas
GET http://localhost:8000/alertas?nivel=CRITICO&ultimas=10
```

### 6. Ver rutas monitoreadas
```bash
GET http://localhost:8000/monitoreando
```

## ⚙️ Configuración de Alertas

El sistema genera alertas automáticas cuando:
- ⚡ **ADVERTENCIA**: Quedan menos de 10 asientos
- ⚠️ **CRÍTICO**: Quedan menos de 5 asientos
- 🚨 **AGOTADO**: No quedan asientos disponibles

Puedes configurar estos umbrales:
```bash
PUT http://localhost:8000/configurar-alertas?umbral_critico=3&umbral_advertencia=8&intervalo_revision=180
```

## 🛠️ Tecnologías

- **FastAPI**: Framework web moderno y rápido
- **httpx**: Cliente HTTP asíncrono
- **uvicorn**: Servidor ASGI de alto rendimiento

## 📊 Estructura de Respuesta
```json
{
  "exito": true,
  "origen": {
    "ciudad": "Barranquilla",
    "id": "195179",
    "nombre_completo": "Barranquilla (Atl) (Todos)"
  },
  "destino": {
    "ciudad": "Medellin",
    "id": "195160",
    "nombre_completo": "Medellin (Ant) (Todos)"
  },
  "fecha": "2025-11-22",
  "total_buses": 13,
  "empresas_disponibles": ["Rápido Ochoa", "Expreso Brasilia"],
  "horarios": [
    {
      "empresa": "Rápido Ochoa",
      "tipo_bus": "Rey Dorado - Lo máximo",
      "hora_salida": "00:30:00",
      "hora_llegada": "11:20:00",
      "duracion_horas": 10.8,
      "precio": 185000,
      "precio_total": 194250,
      "asientos_disponibles": 33,
      "asientos_totales": 38,
      "rating": 3.5,
      "punto_embarque": "Terminal de Barranquilla",
      "punto_desembarque": "Terminal De Medellin"
    }
  ]
}
```

## 👨‍💻 Autor

**Luis - Desarrollador en Rápido Ochoa**

## 📝 Licencia

MIT License

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📧 Contacto

Para preguntas o sugerencias, abre un issue en GitHub.