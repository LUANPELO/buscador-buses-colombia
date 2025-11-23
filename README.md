# 🚌 Buscador de Buses Colombia

API REST para buscar horarios de buses en Colombia con sistema de alertas y monitoreo en tiempo real.

## 👨‍💻 Autor

**Luis Pérez**  
Desarrollador en Rápido Ochoa  
📧 [GitHub](https://github.com/LUANPELO)

---

## 🌟 Características

- ✅ **Búsqueda en tiempo real** - Horarios actualizados desde RedBus
- ✅ **Sistema de alertas** - Notificaciones cuando quedan pocos asientos
- ✅ **Monitoreo automático** - Revisa disponibilidad cada 5 minutos
- ✅ **Filtros avanzados** - Por precio, horario, tipo de bus, rating
- ✅ **49 ciudades** - Todas las rutas de Rápido Ochoa en Colombia
- ✅ **Datos reales** - Asientos disponibles, precios y horarios verificados
- ✅ **API REST completa** - Documentación interactiva con Swagger

---

## 🚀 Tecnologías

- **Python 3.8+**
- **FastAPI** - Framework web moderno y rápido
- **httpx** - Cliente HTTP asíncrono
- **uvicorn** - Servidor ASGI de alto rendimiento

---

## 📦 Instalación

### Requisitos previos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### Pasos de instalación

1. **Clonar el repositorio**
```bash
git clone https://github.com/LUANPELO/buscador-buses-colombia.git
cd buscador-buses-colombia
```

2. **Crear entorno virtual (recomendado)**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Ejecutar el servidor**
```bash
python main.py
```

El servidor estará disponible en: `http://localhost:8000`

---

## 📖 Documentación

### Swagger UI (Documentación interactiva)
```
http://localhost:8000/docs
```

### ReDoc
```
http://localhost:8000/redoc
```

---

## 🎯 Endpoints Principales

### 🔍 Búsqueda de Buses

#### Todas las empresas (para web)
```http
GET /buscar?origen=barranquilla&destino=medellin&fecha=2025-11-23
```

#### Solo Rápido Ochoa (para app móvil)
```http
GET /buscar-rapido-ochoa?origen=barranquilla&destino=medellin&fecha=2025-11-23
```

#### Búsqueda avanzada con filtros
```http
GET /buscar-avanzado?origen=barranquilla&destino=medellin&fecha=2025-11-23&precio_max=200000&hora_min=18:00&solo_ac=true&ordenar_por=precio
```

### 📍 Ciudades Disponibles
```http
GET /ciudades
```

Retorna las 49 ciudades donde opera Rápido Ochoa, organizadas por departamento.

### ⏱️ Verificar Disponibilidad en Tiempo Real
```http
GET /verificar-disponibilidad?origen=barranquilla&destino=medellin&fecha=2025-11-23&hora_salida=19:00
```

### 🔔 Sistema de Alertas

#### Monitorear una ruta
```http
POST /monitorear?origen=barranquilla&destino=medellin&fecha=2025-11-23&horario=19:00&empresa=ochoa
```

#### Ver alertas generadas
```http
GET /alertas?nivel=CRITICO&ultimas=10
```

#### Ver rutas monitoreadas
```http
GET /monitoreando
```

---

## 📊 Ejemplo de Respuesta

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
  "fecha": "2025-11-23",
  "empresa": "Rápido Ochoa",
  "total_buses": 5,
  "horarios": [
    {
      "empresa": "Rápido Ochoa",
      "tipo_bus": "Rey Dorado - Lo máximo",
      "hora_salida": "19:00:00",
      "hora_llegada": "05:50:00",
      "duracion_horas": 10.8,
      "precio": 185000,
      "precio_total": 194250,
      "asientos_disponibles": 33,
      "asientos_totales": 38,
      "rating": 4.2,
      "punto_embarque": "Terminal de Barranquilla",
      "punto_desembarque": "Terminal De Medellin",
      "es_ac": true,
      "es_cama": true
    }
  ]
}
```

---

## 🌍 Ciudades Disponibles

La API cubre **49 ciudades** en Colombia donde opera Rápido Ochoa:

**Antioquia:** Medellín, Caucasia, Jardín, Arboletes, Urrao, Ciudad Bolívar, Puerto Berrío, Rionegro-Marinilla, Betulia, Andes, Giraldo, Yarumal, Bolombolo, Concordia, Tarazá, Caicedo

**Atlántico:** Barranquilla

**Bolívar:** Cartagena, Magangué, San Onofre, Carmen de Bolívar, Mompox

**Caldas:** La Dorada

**Chocó:** Quibdó, Istmina, Condoto, Tutunendo

**Córdoba:** Montería, Planeta Rica, Lorica, Cereté, La Apartada, Chinú, San Antero

**Cundinamarca:** Bogotá

**La Guajira:** Maicao, Riohacha

**Magdalena:** Santa Marta, Ciénaga

**Sucre:** Sincelejo, Coveñas, San Marcos, Tolú, Sahagún

---

## ⚙️ Configuración de Alertas

El sistema genera alertas automáticas cuando:
- ⚡ **ADVERTENCIA**: Quedan menos de 10 asientos
- ⚠️ **CRÍTICO**: Quedan menos de 5 asientos
- 🚨 **AGOTADO**: No quedan asientos disponibles

### Configurar umbrales personalizados
```http
PUT /configurar-alertas?umbral_critico=3&umbral_advertencia=8&intervalo_revision=180
```

---

## 🔧 Filtros Disponibles

| Filtro | Descripción | Ejemplo |
|--------|-------------|---------|
| `empresa` | Filtrar por empresa | `empresa=brasilia` |
| `precio_min` | Precio mínimo | `precio_min=100000` |
| `precio_max` | Precio máximo | `precio_max=200000` |
| `hora_min` | Hora mínima de salida | `hora_min=18:00` |
| `hora_max` | Hora máxima de salida | `hora_max=23:59` |
| `asientos_min` | Mínimo asientos disponibles | `asientos_min=20` |
| `solo_ac` | Solo buses con AC | `solo_ac=true` |
| `solo_cama` | Solo buses tipo cama | `solo_cama=true` |
| `rating_min` | Rating mínimo (0-5) | `rating_min=4.0` |
| `ordenar_por` | Ordenar resultados | `ordenar_por=precio` |

**Opciones de ordenamiento:** `hora`, `precio`, `rating`, `asientos`

---

## 🎨 Casos de Uso

### Para App Móvil Flutter
Usar el endpoint `/buscar-rapido-ochoa` que retorna solo buses de Rápido Ochoa.

### Para Página Web
Usar el endpoint `/buscar` que retorna todas las empresas disponibles.

### Sistema de Monitoreo
Configurar alertas para rutas específicas y recibir notificaciones cuando la disponibilidad cambie.

---

## 🛠️ Desarrollo

### Estructura del Proyecto
```
buscador-buses-colombia/
├── main.py              # Código principal de la API
├── config.py            # Configuración de alertas
├── requirements.txt     # Dependencias
├── test_endpoints.py    # Script de pruebas
├── .gitignore          # Archivos ignorados por Git
├── LICENSE             # Licencia MIT
└── README.md           # Este archivo
```

### Ejecutar Tests
```bash
python test_endpoints.py
```

---

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Para cambios importantes:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📧 Contacto

**Luis Pérez**  
Desarrollador en Rápido Ochoa

Para preguntas o sugerencias, abre un [issue](https://github.com/LUANPELO/buscador-buses-colombia/issues) en GitHub.

---

## 🙏 Agradecimientos

- [RedBus](https://www.redbus.co) - Por proporcionar los datos de horarios
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web utilizado
- [Rápido Ochoa](https://www.rapidoochoa.com/) - Empresa de transporte

---

## 🚀 Roadmap

- [ ] Sistema de reservas interno
- [ ] Integración con pasarela de pagos
- [ ] Notificaciones por email/SMS
- [ ] Panel de administración
- [ ] App móvil Flutter completa
- [ ] API de análisis de rutas más populares

---

**⭐ Si este proyecto te fue útil, considera darle una estrella en GitHub!**
