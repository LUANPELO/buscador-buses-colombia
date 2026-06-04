from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Optional
from datetime import datetime
import asyncio
from config import CONFIG_ALERTAS

app = FastAPI(
    title="Buscador de Buses Colombia - Rápido Ochoa",
    description="API para buscar horarios de buses en Colombia con sistema de alertas",
    version="1.0.2"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = httpx.AsyncClient(timeout=30.0)

rutas_monitoreadas = {}
alertas_generadas = []
estado_anterior = {}

class MonitorRuta:
    def __init__(self, origen: str, destino: str, fecha: str, horario_especifico: Optional[str] = None, empresa_especifica: Optional[str] = None):
        self.origen = origen
        self.destino = destino
        self.fecha = fecha
        self.horario_especifico = horario_especifico
        self.empresa_especifica = empresa_especifica
        self.activo = True
        self.ultima_revision = None
        self.id = f"{origen}_{destino}_{fecha}_{horario_especifico or 'todos'}"

async def revisar_disponibilidad(monitor: MonitorRuta):
    try:
        fecha_redbus = convertir_fecha_a_redbus(monitor.fecha)
        resultado = await buscar_redbus_dinamico(monitor.origen, monitor.destino, fecha_redbus)
        horarios = resultado["resultados"]
        
        if monitor.empresa_especifica:
            horarios = [h for h in horarios if monitor.empresa_especifica.lower() in h["empresa"].lower()]
        
        if monitor.horario_especifico:
            horarios = [h for h in horarios if h["hora_salida"].startswith(monitor.horario_especifico)]
        
        for horario in horarios:
            generar_alerta_si_necesario(monitor, horario)
        
        monitor.ultima_revision = datetime.now()
    except Exception as e:
        print(f"Error revisando ruta {monitor.id}: {e}")

def generar_alerta_si_necesario(monitor: MonitorRuta, horario: Dict):
    asientos_disponibles = horario["asientos_disponibles"]
    key = f"{monitor.id}_{horario['hora_salida']}_{horario['empresa']}"
    
    estado_prev = estado_anterior.get(key, {})
    asientos_prev = estado_prev.get("asientos", None)
    
    estado_anterior[key] = {"asientos": asientos_disponibles, "timestamp": datetime.now()}
    
    alerta = None
    
    if asientos_disponibles == 0 and asientos_prev != 0:
        alerta = {
            "tipo": "AGOTADO",
            "nivel": "CRITICO",
            "mensaje": f"🚨 SIN PUESTOS: {horario['empresa']} - {horario['hora_salida']}",
            "origen": monitor.origen,
            "destino": monitor.destino,
            "fecha": monitor.fecha,
            "empresa": horario["empresa"],
            "hora_salida": horario["hora_salida"],
            "asientos_disponibles": asientos_disponibles,
            "asientos_totales": horario["asientos_totales"],
            "precio": horario["precio_total"],
            "timestamp": datetime.now().isoformat()
        }
    elif 0 < asientos_disponibles <= CONFIG_ALERTAS["umbral_critico"]:
        if asientos_prev is None or asientos_prev > CONFIG_ALERTAS["umbral_critico"]:
            alerta = {
                "tipo": "CRITICO",
                "nivel": "ALTO",
                "mensaje": f"⚠️ QUEDAN SOLO {asientos_disponibles} PUESTOS: {horario['empresa']} - {horario['hora_salida']}",
                "origen": monitor.origen,
                "destino": monitor.destino,
                "fecha": monitor.fecha,
                "empresa": horario["empresa"],
                "hora_salida": horario["hora_salida"],
                "asientos_disponibles": asientos_disponibles,
                "asientos_totales": horario["asientos_totales"],
                "precio": horario["precio_total"],
                "timestamp": datetime.now().isoformat()
            }
    elif CONFIG_ALERTAS["umbral_critico"] < asientos_disponibles <= CONFIG_ALERTAS["umbral_advertencia"]:
        if asientos_prev is None or asientos_prev > CONFIG_ALERTAS["umbral_advertencia"]:
            alerta = {
                "tipo": "ADVERTENCIA",
                "nivel": "MEDIO",
                "mensaje": f"⚡ Quedan {asientos_disponibles} puestos: {horario['empresa']} - {horario['hora_salida']}",
                "origen": monitor.origen,
                "destino": monitor.destino,
                "fecha": monitor.fecha,
                "empresa": horario["empresa"],
                "hora_salida": horario["hora_salida"],
                "asientos_disponibles": asientos_disponibles,
                "asientos_totales": horario["asientos_totales"],
                "precio": horario["precio_total"],
                "timestamp": datetime.now().isoformat()
            }
    
    if alerta:
        alertas_generadas.append(alerta)
        print(f"🔔 ALERTA: {alerta['mensaje']}")

async def monitor_loop():
    while True:
        try:
            for monitor_id, monitor in list(rutas_monitoreadas.items()):
                if monitor.activo:
                    await revisar_disponibilidad(monitor)
            await asyncio.sleep(CONFIG_ALERTAS["intervalo_revision"])
        except Exception as e:
            print(f"Error en monitor loop: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_loop())
    print("🚀 Sistema de monitoreo iniciado")

async def buscar_ciudad_redbus(nombre_ciudad: str) -> Optional[Dict]:
    ciudades_principales = {
        "medellin": {"id": "195160", "name": "Medellin (Ant) (Todos)"},
        "caucasia": {"id": "195150", "name": "Caucasia (Ant) (Todos)"},
        "jardin": {"id": "195158", "name": "Jardin (Ant) (Todos)"},
        "arboletes": {"id": "195102", "name": "Arboletes (Ant) (Todos)"},
        "urrao": {"id": "195175", "name": "Urrao (Ant) (Todos)"},
        "ciudad bolivar": {"id": "195153", "name": "Ciudad Bolivar (Ant) (Todos)"},
        "puerto berrio": {"id": "196351", "name": "Puerto Berrio (Ant) (Todos)"},
        "rionegro": {"id": "202962", "name": "Rionegro (Ant) (Todos)"},
        "marinilla": {"id": "202962", "name": "Rionegro (Ant) (Todos)"},
        "betulia": {"id": "195489", "name": "Betulia (Ant) (Todos)"},
        "andes": {"id": "195488", "name": "Andes (Ant) (Todos)"},
        "giraldo": {"id": "195157", "name": "Giraldo (Ant) (Todos)"},
        "yarumal": {"id": "195545", "name": "Yarumal (Ant) (Todos)"},
        "bolombolo": {"id": "195490", "name": "Bolombolo (Ant) (Todos)"},
        "concordia": {"id": "195500", "name": "Concordia (Ant) (Todos)"},
        "taraza": {"id": "195540", "name": "Taraza (Ant) (Todos)"},
        "caicedo": {"id": "195491", "name": "Caicedo (Ant) (Todos)"},
        "santa rosa de osos": {"id": "195816", "name": "Santa Rosa De Osos (Ant) (Todos)"},
        "monteria": {"id": "195200", "name": "Monteria (Cor) (Todos)"},
        "planeta rica": {"id": "195548", "name": "Planeta Rica (Cor) (Todos)"},
        "lorica": {"id": "194924", "name": "Lorica (Cor) (Todos)"},
        "cerete": {"id": "196158", "name": "Cerete (Cor) (Todos)"},
        "la apartada": {"id": "195547", "name": "La Apartada (Cor) (Todos)"},
        "chinu": {"id": "195541", "name": "Chinu (Cor) (Todos)"},
        "san antero": {"id": "196364", "name": "San Antero (Cor) (Todos)"},
        "sahagun": {"id": "195550", "name": "Sahagun (Cor) (Todos)"},
        "sincelejo": {"id": "195243", "name": "Sincelejo (Suc) (Todos)"},
        "covenas": {"id": "196179", "name": "Covenas (Suc) (Todos)"},
        "san marcos": {"id": "195565", "name": "San Marcos (Suc) (Todos)"},
        "tolu": {"id": "196394", "name": "Tolu (Suc) (Todos)"},
        "barranquilla": {"id": "195179", "name": "Barranquilla (Atl) (Todos)"},
        "quibdo": {"id": "195175", "name": "Quibdo (Cho) (Todos)"},
        "istmina": {"id": "196805", "name": "Istmina (Cho) (Todos)"},
        "condoto": {"id": "195199", "name": "Condoto (Cho) (Todos)"},
        "tutunendo": {"id": "195531", "name": "Tutunendo (Cho) (Todos)"},
        "santa marta": {"id": "195215", "name": "Santa Marta (Mag) (Todos)"},
        "santamarta": {"id": "195215", "name": "Santa Marta (Mag) (Todos)"},
        "cienaga": {"id": "195553", "name": "Cienaga (Mag) (Todos)"},
        "palomino": {"id": "196333", "name": "Palomino (Guaj) (Todos)"},
        "maicao": {"id": "195205", "name": "Maicao (Guaj) (Todos)"},
        "riohacha": {"id": "195204", "name": "Riohacha (Guaj) (Todos)"},
        "la dorada": {"id": "195187", "name": "La Dorada (Cal) (Todos)"},
        "cartagena": {"id": "195181", "name": "Cartagena (Bol) (Todos)"},
        "magangue": {"id": "196300", "name": "Magangue (Bol) (Todos)"},
        "san onofre": {"id": "195566", "name": "San Onofre (Suc) (Todos)"},
        "carmen de bolivar": {"id": "195800", "name": "Carmen De Bolivar (Bol) (Todos)"},
        "mompox": {"id": "195833", "name": "Mompox (Bol) (Todos)"},
        "bogota": {"id": "195201", "name": "Bogota (D.C) (Todos)"},
    }
    
    nombre_lower = nombre_ciudad.lower().strip()
    if nombre_lower in ciudades_principales:
        return ciudades_principales[nombre_lower]
    
    url = "https://www.redbus.co/Home/SolarSearch"
    params = {
        "search": nombre_ciudad,
        "parentLocationId": "195120",
        "parentId": "195160",
        "parentLocationType": "CITY",
        "state": "null",
        "enableSolrCityId": "false"
    }
    headers = {
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0"
    }
    
    try:
        response = await client.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                if doc.get("locationType") == "CITY":
                    return {"id": str(doc.get("ID")), "name": doc.get("Name")}
            if docs and len(docs) > 0:
                return {"id": str(docs[0].get("ID")), "name": docs[0].get("Name")}
        return None
    except Exception as e:
        print(f"Error buscando ciudad: {e}")
        return None

async def buscar_redbus_dinamico(origen: str, destino: str, fecha: str):
    """Busca en redBus con paginación — nuevo endpoint POST /rpw/api/searchResults"""
    origen_data = await buscar_ciudad_redbus(origen)
    destino_data = await buscar_ciudad_redbus(destino)
    
    if not origen_data:
        raise HTTPException(404, f"No se encontró la ciudad origen: {origen}")
    if not destino_data:
        raise HTTPException(404, f"No se encontró la ciudad destino: {destino}")
    
    todos_los_buses = []
    offset = 0
    limit = 100
    max_paginas = 5

    # Nuevo endpoint RedBus (POST con body JSON de filtros)
    url = "https://www.redbus.co/rpw/api/searchResults"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": "https://www.redbus.co",
        "referer": "https://www.redbus.co/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    }
    body = {
        "appliedFilterCount": 0,
        "onlyShow": [], "dt": [], "SeaterType": [], "AcType": [],
        "travelsList": [], "amtList": [], "at": [], "bcf": [],
        "bpIdentifier": [], "bpKeys": [], "bpList": [],
        "dpIdentifier": [], "dpKeys": [], "dpList": [],
        "RouteIds": [], "CampaignFilter": [], "opBusTypeFilterList": [],
        "persuasionList": [], "preRouteFilters": None,
        "priceRange": [], "streaksFilter": []
    }

    for pagina in range(max_paginas):
        params = {
            "fromCity": origen_data["id"],
            "toCity": destino_data["id"],
            "DOJ": fecha,
            "limit": str(limit),
            "offset": str(offset),
            "meta": "true",
            "groupId": "0",
            "sectionId": "0",
            "sort": "0",
            "sortOrder": "0",
            "from": "initialLoad" if pagina == 0 else "pagination",
            "getUuid": "true",
            "bT": "1",
            "clearLMBFilter": "undefined",
            "isFilterApplied": "false",
        }

        try:
            response = await client.post(url, params=params, json=body, headers=headers)

            if response.status_code == 200:
                data = response.json()
                inventories = data.get("data", {}).get("inventories", [])
                total_count = data.get("data", {}).get("metaData", {}).get("totalCount", 0)

                print(f"🔍 Página {pagina + 1}: {len(inventories)} buses | total: {total_count} | offset: {offset}")

                if not inventories:
                    break

                buses_pagina = normalizar_resultados_redbus({"inventories": inventories})
                todos_los_buses.extend(buses_pagina)

                if len(todos_los_buses) >= total_count:
                    break

                offset += limit
            else:
                print(f"⚠️ Error HTTP {response.status_code} en página {pagina + 1}")
                break

        except Exception as e:
            print(f"❌ Error en página {pagina + 1}: {e}")
            break

    return {
        "origen": origen_data,
        "destino": destino_data,
        "resultados": todos_los_buses
    }

def normalizar_resultados_redbus(data: dict) -> List[Dict]:
    resultados = []
    inventories = data.get("inventories", [])
    for bus in inventories:
        try:
            resultado = {
                "empresa": bus.get("travelsName", "N/A"),
                "tipo_bus": bus.get("busType", "N/A"),
                "servicio": bus.get("serviceName", "N/A"),
                "hora_salida": bus.get("departureTime", "").split(" ")[1] if bus.get("departureTime") else "N/A",
                "hora_llegada": bus.get("arrivalTime", "").split(" ")[1] if bus.get("arrivalTime") else "N/A",
                "fecha_salida": bus.get("departureTime", "N/A"),
                "fecha_llegada": bus.get("arrivalTime", "N/A"),
                "duracion_minutos": bus.get("journeyDurationMin", 0),
                "duracion_horas": round(bus.get("journeyDurationMin", 0) / 60, 1),
                "precio": bus.get("fareList", [0])[0] if bus.get("fareList") else 0,
                "tarifa_servicio": bus.get("convenienceFee", 0),
                "precio_total": bus.get("fareList", [0])[0] + bus.get("convenienceFee", 0) if bus.get("fareList") else 0,
                "moneda": bus.get("vendorCurrency", "COP"),
                "asientos_disponibles": bus.get("availableSeats", 0),
                "asientos_totales": bus.get("totalSeats", 0),
                "asientos_ventana": bus.get("availableWindowSeats", 0),
                "punto_embarque": bus.get("standardBpName", "N/A"),
                "punto_desembarque": bus.get("standardDpName", "N/A"),
                "rating": bus.get("totalRatings", 0),
                "num_reviews": bus.get("numberOfReviews", "0"),
                "es_ac": bus.get("isAc", False),
                "es_cama": bus.get("isSleeper", False),
                "tiene_tracking": bus.get("isLiveTrackingAvailable", False),
                "agotado": bus.get("isSoldOut", False),
            }
            resultados.append(resultado)
        except Exception as e:
            continue
    return resultados

def convertir_fecha_a_redbus(fecha_input: str) -> str:
    try:
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]:
            try:
                fecha = datetime.strptime(fecha_input, fmt)
                meses = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
                return f"{fecha.day:02d}-{meses[fecha.month]}-{fecha.year}"
            except:
                continue
        if len(fecha_input.split("-")) == 3 and len(fecha_input.split("-")[1]) == 3:
            return fecha_input
        raise ValueError("Formato de fecha no válido")
    except:
        raise HTTPException(400, "Formato de fecha inválido")

def agrupar_por_departamento(ciudades):
    departamentos = {}
    for ciudad in ciudades:
        dept = ciudad["departamento"]
        if dept not in departamentos:
            departamentos[dept] = []
        departamentos[dept].append({"nombre": ciudad["nombre"], "slug": ciudad["slug"]})
    return departamentos

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Buscador Buses Colombia",
        "version": "1.0.2"
    }

@app.get("/")
async def root():
    return {
        "nombre": "🚌 Buscador de Buses Colombia - Rápido Ochoa",
        "version": "1.0.2",
        "descripcion": "API con paginación completa",
        "autor": "Luis Pérez",
        "endpoints": {
            "GET /": "Info",
            "GET /health": "Health check (mantener activa)",
            "GET /ciudades": "Ciudades",
            "GET /buscar": "Todas empresas",
            "GET /buscar-rapido-ochoa": "Solo Ochoa",
            "GET /buscar-avanzado": "Filtros",
            "GET /verificar-disponibilidad": "Tiempo real",
            "POST /monitorear": "Monitorear",
            "GET /alertas": "Alertas"
        },
        "docs": "/docs"
    }

@app.get("/ciudades")
async def obtener_ciudades():
    ciudades = [
        {"nombre": "Medellín", "departamento": "Antioquia", "slug": "medellin"},
        {"nombre": "Caucasia", "departamento": "Antioquia", "slug": "caucasia"},
        {"nombre": "Jardín", "departamento": "Antioquia", "slug": "jardin"},
        {"nombre": "Arboletes", "departamento": "Antioquia", "slug": "arboletes"},
        {"nombre": "Urrao", "departamento": "Antioquia", "slug": "urrao"},
        {"nombre": "Ciudad Bolívar", "departamento": "Antioquia", "slug": "ciudad bolivar"},
        {"nombre": "Puerto Berrío", "departamento": "Antioquia", "slug": "puerto berrio"},
        {"nombre": "Rionegro - Marinilla", "departamento": "Antioquia", "slug": "rionegro"},
        {"nombre": "Betulia", "departamento": "Antioquia", "slug": "betulia"},
        {"nombre": "Andes", "departamento": "Antioquia", "slug": "andes"},
        {"nombre": "Giraldo", "departamento": "Antioquia", "slug": "giraldo"},
        {"nombre": "Yarumal", "departamento": "Antioquia", "slug": "yarumal"},
        {"nombre": "Bolombolo", "departamento": "Antioquia", "slug": "bolombolo"},
        {"nombre": "Concordia", "departamento": "Antioquia", "slug": "concordia"},
        {"nombre": "Tarazá", "departamento": "Antioquia", "slug": "taraza"},
        {"nombre": "Caicedo", "departamento": "Antioquia", "slug": "caicedo"},
        {"nombre": "Barranquilla", "departamento": "Atlántico", "slug": "barranquilla"},
        {"nombre": "Cartagena", "departamento": "Bolívar", "slug": "cartagena"},
        {"nombre": "Magangué", "departamento": "Bolívar", "slug": "magangue"},
        {"nombre": "San Onofre", "departamento": "Bolívar", "slug": "san onofre"},
        {"nombre": "Carmen de Bolívar", "departamento": "Bolívar", "slug": "carmen de bolivar"},
        {"nombre": "Mompox", "departamento": "Bolívar", "slug": "mompox"},
        {"nombre": "La Dorada", "departamento": "Caldas", "slug": "la dorada"},
        {"nombre": "Quibdó", "departamento": "Chocó", "slug": "quibdo"},
        {"nombre": "Istmina", "departamento": "Chocó", "slug": "istmina"},
        {"nombre": "Condoto", "departamento": "Chocó", "slug": "condoto"},
        {"nombre": "Tutunendo", "departamento": "Chocó", "slug": "tutunendo"},
        {"nombre": "Montería", "departamento": "Córdoba", "slug": "monteria"},
        {"nombre": "Planeta Rica", "departamento": "Córdoba", "slug": "planeta rica"},
        {"nombre": "Lorica", "departamento": "Córdoba", "slug": "lorica"},
        {"nombre": "Cereté", "departamento": "Córdoba", "slug": "cerete"},
        {"nombre": "La Apartada", "departamento": "Córdoba", "slug": "la apartada"},
        {"nombre": "Chinú", "departamento": "Córdoba", "slug": "chinu"},
        {"nombre": "San Antero", "departamento": "Córdoba", "slug": "san antero"},
        {"nombre": "Bogotá", "departamento": "Cundinamarca", "slug": "bogota"},
        {"nombre": "Maicao", "departamento": "La Guajira", "slug": "maicao"},
        {"nombre": "Riohacha", "departamento": "La Guajira", "slug": "riohacha"},
        {"nombre": "Santa Marta", "departamento": "Magdalena", "slug": "santa marta"},
        {"nombre": "Ciénaga", "departamento": "Magdalena", "slug": "cienaga"},
        {"nombre": "Sincelejo", "departamento": "Sucre", "slug": "sincelejo"},
        {"nombre": "Coveñas", "departamento": "Sucre", "slug": "covenas"},
        {"nombre": "San Marcos", "departamento": "Sucre", "slug": "san marcos"},
        {"nombre": "Tolú", "departamento": "Sucre", "slug": "tolu"},
        {"nombre": "Sahagún", "departamento": "Sucre", "slug": "sahagun"},
    ]
    return {
        "total": len(ciudades),
        "ciudades": sorted(ciudades, key=lambda x: x["nombre"]),
        "por_departamento": agrupar_por_departamento(ciudades)
    }

@app.get("/buscar")
async def endpoint_buscar(origen: str, destino: str, fecha: str, empresa: Optional[str] = None):
    fecha_redbus = convertir_fecha_a_redbus(fecha)
    resultado = await buscar_redbus_dinamico(origen, destino, fecha_redbus)
    resultados = resultado["resultados"]
    if empresa:
        resultados = [r for r in resultados if empresa.lower() in r["empresa"].lower()]
    resultados.sort(key=lambda x: x["hora_salida"])
    empresas_disponibles = list(set([r["empresa"] for r in resultados]))
    return {
        "exito": True,
        "origen": {"ciudad": origen.title(), "id": resultado["origen"]["id"], "nombre_completo": resultado["origen"]["name"]},
        "destino": {"ciudad": destino.title(), "id": resultado["destino"]["id"], "nombre_completo": resultado["destino"]["name"]},
        "fecha": fecha,
        "total_buses": len(resultados),
        "empresas_disponibles": sorted(empresas_disponibles),
        "horarios": resultados
    }

@app.get("/buscar-rapido-ochoa")
async def buscar_solo_rapido_ochoa(origen: str, destino: str, fecha: str):
    fecha_redbus = convertir_fecha_a_redbus(fecha)
    resultado = await buscar_redbus_dinamico(origen, destino, fecha_redbus)
    buses_ochoa = [bus for bus in resultado["resultados"] if "ochoa" in bus["empresa"].lower()]
    buses_ochoa.sort(key=lambda x: x["hora_salida"])
    return {
        "exito": True,
        "origen": {"ciudad": origen.title(), "id": resultado["origen"]["id"], "nombre_completo": resultado["origen"]["name"]},
        "destino": {"ciudad": destino.title(), "id": resultado["destino"]["id"], "nombre_completo": resultado["destino"]["name"]},
        "fecha": fecha,
        "empresa": "Rápido Ochoa",
        "total_buses": len(buses_ochoa),
        "horarios": buses_ochoa
    }

@app.get("/verificar-disponibilidad")
async def verificar_disponibilidad(origen: str, destino: str, fecha: str, hora_salida: str):
    fecha_redbus = convertir_fecha_a_redbus(fecha)
    resultado = await buscar_redbus_dinamico(origen, destino, fecha_redbus)
    if len(hora_salida.split(":")) == 2:
        hora_salida += ":00"
    bus_encontrado = None
    for bus in resultado["resultados"]:
        if bus["hora_salida"] == hora_salida:
            bus_encontrado = bus
            break
    if bus_encontrado:
        return {
            "disponible": bus_encontrado["asientos_disponibles"] > 0,
            "asientos_disponibles": bus_encontrado["asientos_disponibles"],
            "asientos_totales": bus_encontrado["asientos_totales"],
            "precio": bus_encontrado["precio_total"],
            "estado": "DISPONIBLE" if bus_encontrado["asientos_disponibles"] > 10 else "POCOS ASIENTOS" if bus_encontrado["asientos_disponibles"] > 0 else "AGOTADO",
            "bus": bus_encontrado
        }
    return {"disponible": False, "mensaje": "Bus no encontrado"}

@app.get("/buscar-avanzado")
async def endpoint_buscar_avanzado(
    origen: str, destino: str, fecha: str,
    empresa: Optional[str] = None,
    precio_min: Optional[int] = None,
    precio_max: Optional[int] = None,
    hora_min: Optional[str] = None,
    hora_max: Optional[str] = None,
    asientos_min: Optional[int] = None,
    solo_ac: Optional[bool] = None,
    solo_cama: Optional[bool] = None,
    rating_min: Optional[float] = None,
    ordenar_por: Optional[str] = "hora"
):
    fecha_redbus = convertir_fecha_a_redbus(fecha)
    resultado = await buscar_redbus_dinamico(origen, destino, fecha_redbus)
    resultados = resultado["resultados"]
    
    if empresa:
        resultados = [r for r in resultados if empresa.lower() in r["empresa"].lower()]
    if precio_min is not None:
        resultados = [r for r in resultados if r["precio_total"] >= precio_min]
    if precio_max is not None:
        resultados = [r for r in resultados if r["precio_total"] <= precio_max]
    if hora_min:
        resultados = [r for r in resultados if r["hora_salida"] >= hora_min]
    if hora_max:
        resultados = [r for r in resultados if r["hora_salida"] <= hora_max]
    if asientos_min is not None:
        resultados = [r for r in resultados if r["asientos_disponibles"] >= asientos_min]
    if solo_ac:
        resultados = [r for r in resultados if r["es_ac"]]
    if solo_cama:
        resultados = [r for r in resultados if r["es_cama"]]
    if rating_min is not None:
        resultados = [r for r in resultados if r["rating"] >= rating_min]
    
    if ordenar_por == "precio":
        resultados.sort(key=lambda x: x["precio_total"])
    elif ordenar_por == "duracion":
        resultados.sort(key=lambda x: x["duracion_minutos"])
    elif ordenar_por == "rating":
        resultados.sort(key=lambda x: x["rating"], reverse=True)
    else:
        resultados.sort(key=lambda x: x["hora_salida"])
    
    return {
        "exito": True,
        "origen": {"ciudad": origen.title(), "id": resultado["origen"]["id"], "nombre_completo": resultado["origen"]["name"]},
        "destino": {"ciudad": destino.title(), "id": resultado["destino"]["id"], "nombre_completo": resultado["destino"]["name"]},
        "fecha": fecha,
        "filtros_aplicados": {
            "empresa": empresa, "precio_min": precio_min, "precio_max": precio_max,
            "hora_min": hora_min, "hora_max": hora_max, "asientos_min": asientos_min,
            "solo_ac": solo_ac, "solo_cama": solo_cama, "rating_min": rating_min,
            "ordenar_por": ordenar_por
        },
        "total_buses": len(resultados),
        "horarios": resultados
    }

@app.post("/monitorear")
async def crear_monitor(
    origen: str, destino: str, fecha: str,
    horario_especifico: Optional[str] = None,
    empresa_especifica: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    monitor = MonitorRuta(origen, destino, fecha, horario_especifico, empresa_especifica)
    rutas_monitoreadas[monitor.id] = monitor
    return {
        "exito": True,
        "mensaje": "Monitoreo iniciado",
        "monitor_id": monitor.id,
        "detalles": {"origen": origen, "destino": destino, "fecha": fecha,
                     "horario_especifico": horario_especifico, "empresa_especifica": empresa_especifica},
        "configuracion": CONFIG_ALERTAS
    }

@app.delete("/monitorear/{monitor_id}")
async def detener_monitor(monitor_id: str):
    if monitor_id in rutas_monitoreadas:
        rutas_monitoreadas[monitor_id].activo = False
        del rutas_monitoreadas[monitor_id]
        return {"exito": True, "mensaje": f"Monitor {monitor_id} detenido"}
    raise HTTPException(404, "Monitor no encontrado")

@app.get("/monitores")
async def listar_monitores():
    monitores = []
    for monitor_id, monitor in rutas_monitoreadas.items():
        monitores.append({
            "id": monitor.id, "origen": monitor.origen, "destino": monitor.destino,
            "fecha": monitor.fecha, "horario_especifico": monitor.horario_especifico,
            "empresa_especifica": monitor.empresa_especifica, "activo": monitor.activo,
            "ultima_revision": monitor.ultima_revision.isoformat() if monitor.ultima_revision else None
        })
    return {"total": len(monitores), "monitores": monitores}

@app.get("/alertas")
async def obtener_alertas(limite: int = 50):
    return {"total": len(alertas_generadas), "alertas": alertas_generadas[-limite:]}

@app.delete("/alertas")
async def limpiar_alertas():
    alertas_generadas.clear()
    return {"exito": True, "mensaje": "Alertas limpiadas"}
