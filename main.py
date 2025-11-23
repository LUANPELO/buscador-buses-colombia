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
    version="1.0.0"
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
    def __init__(self, origen: str, destino: str, fecha: str, 
                 horario_especifico: Optional[str] = None,
                 empresa_especifica: Optional[str] = None):
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
            "tipo": "AGOTADO", "nivel": "CRITICO",
            "mensaje": f"🚨 SIN PUESTOS: {horario['empresa']} - {horario['hora_salida']}",
            "origen": monitor.origen, "destino": monitor.destino, "fecha": monitor.fecha,
            "empresa": horario["empresa"], "hora_salida": horario["hora_salida"],
            "asientos_disponibles": asientos_disponibles, "asientos_totales": horario["asientos_totales"],
            "precio": horario["precio_total"], "timestamp": datetime.now().isoformat()
        }
    elif 0 < asientos_disponibles <= CONFIG_ALERTAS["umbral_critico"]:
        if asientos_prev is None or asientos_prev > CONFIG_ALERTAS["umbral_critico"]:
            alerta = {
                "tipo": "CRITICO", "nivel": "ALTO",
                "mensaje": f"⚠️ QUEDAN SOLO {asientos_disponibles} PUESTOS: {horario['empresa']} - {horario['hora_salida']}",
                "origen": monitor.origen, "destino": monitor.destino, "fecha": monitor.fecha,
                "empresa": horario["empresa"], "hora_salida": horario["hora_salida"],
                "asientos_disponibles": asientos_disponibles, "asientos_totales": horario["asientos_totales"],
                "precio": horario["precio_total"], "timestamp": datetime.now().isoformat()
            }
    elif CONFIG_ALERTAS["umbral_critico"] < asientos_disponibles <= CONFIG_ALERTAS["umbral_advertencia"]:
        if asientos_prev is None or asientos_prev > CONFIG_ALERTAS["umbral_advertencia"]:
            alerta = {
                "tipo": "ADVERTENCIA", "nivel": "MEDIO",
                "mensaje": f"⚡ Quedan {asientos_disponibles} puestos: {horario['empresa']} - {horario['hora_salida']}",
                "origen": monitor.origen, "destino": monitor.destino, "fecha": monitor.fecha,
                "empresa": horario["empresa"], "hora_salida": horario["hora_salida"],
                "asientos_disponibles": asientos_disponibles, "asientos_totales": horario["asientos_totales"],
                "precio": horario["precio_total"], "timestamp": datetime.now().isoformat()
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
        "caucasia": {"id": "195146", "name": "Caucasia (Ant) (Todos)"},
        "jardin": {"id": "197119", "name": "Jardin (Ant) (Todos)"},
        "arboletes": {"id": "197095", "name": "Arboletes (Ant) (Todos)"},
        "urrao": {"id": "197158", "name": "Urrao (Ant) (Todos)"},
        "ciudad bolivar": {"id": "197104", "name": "Ciudad Bolivar (Ant) (Todos)"},
        "puerto berrio": {"id": "197141", "name": "Puerto Berrio (Ant) (Todos)"},
        "rionegro": {"id": "197143", "name": "Rionegro - Marinilla (Ant) (Todos)"},
        "marinilla": {"id": "197143", "name": "Rionegro - Marinilla (Ant) (Todos)"},
        "betulia": {"id": "197100", "name": "Betulia (Ant) (Todos)"},
        "andes": {"id": "197094", "name": "Andes (Ant) (Todos)"},
        "giraldo": {"id": "197113", "name": "Giraldo (Ant) (Todos)"},
        "yarumal": {"id": "197162", "name": "Yarumal (Ant) (Todos)"},
        "bolombolo": {"id": "197101", "name": "Bolombolo (Ant) (Todos)"},
        "concordia": {"id": "197106", "name": "Concordia (Ant) (Todos)"},
        "taraza": {"id": "197154", "name": "Taraza (Ant) (Todos)"},
        "caicedo": {"id": "197102", "name": "Caicedo (Ant) (Todos)"},
        "monteria": {"id": "195164", "name": "Monteria (Cor) (Todos)"},
        "planeta rica": {"id": "197138", "name": "Planeta Rica (Cor) (Todos)"},
        "lorica": {"id": "197127", "name": "Lorica (Cor) (Todos)"},
        "cerete": {"id": "197103", "name": "Cerete (Cor) (Todos)"},
        "la apartada": {"id": "197122", "name": "La Apartada (Cor) (Todos)"},
        "chinu": {"id": "197105", "name": "Chinu (Cor) (Todos)"},
        "san antero": {"id": "197147", "name": "San Antero (Cor) (Todos)"},
        "sincelejo": {"id": "195187", "name": "Sincelejo (Suc) (Todos)"},
        "covenas": {"id": "197107", "name": "Covenas (Suc) (Todos)"},
        "san marcos": {"id": "197148", "name": "San Marcos (Suc) (Todos)"},
        "tolu": {"id": "197156", "name": "Tolu (Suc) (Todos)"},
        "sahagun": {"id": "197145", "name": "Sahagun (Suc) (Todos)"},
        "barranquilla": {"id": "195179", "name": "Barranquilla (Atl) (Todos)"},
        "quibdo": {"id": "195175", "name": "Quibdo (Cho) (Todos)"},
        "istmina": {"id": "197121", "name": "Istmina (Cho) (Todos)"},
        "condoto": {"id": "197106", "name": "Condoto (Cho) (Todos)"},
        "tutunendo": {"id": "197157", "name": "Tutunendo (Cho) (Todos)"},
        "santa marta": {"id": "195189", "name": "Santa Marta (Mag) (Todos)"},
        "santamarta": {"id": "195189", "name": "Santa Marta (Mag) (Todos)"},
        "cienaga": {"id": "197104", "name": "Cienaga (Mag) (Todos)"},
        "maicao": {"id": "197128", "name": "Maicao (Gua) (Todos)"},
        "riohacha": {"id": "195178", "name": "Riohacha (Gua) (Todos)"},
        "la dorada": {"id": "197123", "name": "La Dorada (Cal) (Todos)"},
        "cartagena": {"id": "195181", "name": "Cartagena (Bol) (Todos)"},
        "magangue": {"id": "197129", "name": "Magangue (Bol) (Todos)"},
        "san onofre": {"id": "197149", "name": "San Onofre (Bol) (Todos)"},
        "carmen de bolivar": {"id": "197102", "name": "Carmen De Bolivar (Bol) (Todos)"},
        "mompox": {"id": "197133", "name": "Mompox (Bol) (Todos)"},
        "bogota": {"id": "195201", "name": "Bogota (D.C) (Todos)"},
    }
    
    nombre_lower = nombre_ciudad.lower().strip()
    if nombre_lower in ciudades_principales:
        return ciudades_principales[nombre_lower]
    
    url = "https://www.redbus.co/Home/SolarSearch"
    params = {"search": nombre_ciudad, "parentLocationId": "195120", "parentId": "195160", "parentLocationType": "CITY", "state": "null", "enableSolrCityId": "false"}
    headers = {"accept": "application/json, text/plain, */*", "user-agent": "Mozilla/5.0"}
    
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
    origen_data = await buscar_ciudad_redbus(origen)
    destino_data = await buscar_ciudad_redbus(destino)
    
    if not origen_data:
        raise HTTPException(404, f"No se encontró la ciudad origen: {origen}")
    if not destino_data:
        raise HTTPException(404, f"No se encontró la ciudad destino: {destino}")
    
    url = "https://www.redbus.co/search/SearchV4Results"
    params = {"fromCity": origen_data["id"], "toCity": destino_data["id"], "src": origen_data["name"], "dst": destino_data["name"], "DOJ": fecha, "sectionId": "0", "groupId": "0", "limit": "500", "offset": "0", "sort": "0", "sortOrder": "0", "meta": "true", "returnSearch": "0"}
    headers = {"accept": "application/json, text/plain, */*", "content-type": "application/json", "origin": "https://www.redbus.co", "user-agent": "Mozilla/5.0"}
    payload = {"AcType": [], "CampaignFilter": [], "SeaterType": [], "amtList": [], "at": [], "bcf": [], "bpIdentifier": [], "bpList": [], "dpList": [], "dt": [], "onlyShow": [], "opBusTypeFilterList": [], "persuasionList": [], "rtcBusTypeList": [], "travelsList": []}
    
    try:
        response = await client.post(url, params=params, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {"origen": origen_data, "destino": destino_data, "resultados": normalizar_resultados_redbus(data)}
        else:
            raise HTTPException(response.status_code, f"Error en redBus")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")


def normalizar_resultados_redbus(data: dict) -> List[Dict]:
    resultados = []
    inventories = data.get("inventories", [])
    for bus in inventories:
        try:
            resultado = {
                "empresa": bus.get("travelsName", "N/A"), "tipo_bus": bus.get("busType", "N/A"), "servicio": bus.get("serviceName", "N/A"),
                "hora_salida": bus.get("departureTime", "").split(" ")[1] if bus.get("departureTime") else "N/A",
                "hora_llegada": bus.get("arrivalTime", "").split(" ")[1] if bus.get("arrivalTime") else "N/A",
                "fecha_salida": bus.get("departureTime", "N/A"), "fecha_llegada": bus.get("arrivalTime", "N/A"),
                "duracion_minutos": bus.get("journeyDurationMin", 0), "duracion_horas": round(bus.get("journeyDurationMin", 0) / 60, 1),
                "precio": bus.get("fareList", [0])[0] if bus.get("fareList") else 0, "tarifa_servicio": bus.get("convenienceFee", 0),
                "precio_total": bus.get("fareList", [0])[0] + bus.get("convenienceFee", 0) if bus.get("fareList") else 0,
                "moneda": bus.get("vendorCurrency", "COP"), "asientos_disponibles": bus.get("availableSeats", 0),
                "asientos_totales": bus.get("totalSeats", 0), "asientos_ventana": bus.get("availableWindowSeats", 0),
                "punto_embarque": bus.get("bpData", [{}])[0].get("Name", "N/A") if bus.get("bpData") else "N/A",
                "punto_desembarque": bus.get("dpData", [{}])[0].get("Name", "N/A") if bus.get("dpData") else "N/A",
                "rating": bus.get("totalRatings", 0), "num_reviews": bus.get("numberOfReviews", "0"),
                "es_ac": bus.get("isAc", False), "es_cama": bus.get("isSleeper", False),
                "tiene_tracking": bus.get("isLiveTrackingAvailable", False), "agotado": bus.get("isSoldOut", False),
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
                meses = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
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


@app.get("/")
async def root():
    return {
        "nombre": "🚌 Buscador de Buses Colombia - Rápido Ochoa", "version": "1.0.0",
        "descripcion": "API para buscar horarios de buses con sistema de alertas", "autor": "Luis - Rápido Ochoa",
        "endpoints": {"GET /": "Info API", "GET /ciudades": "Ciudades Rápido Ochoa", "GET /buscar": "Todas empresas (web)", "GET /buscar-rapido-ochoa": "Solo Ochoa (app)", "GET /buscar-avanzado": "Filtros avanzados", "GET /verificar-disponibilidad": "Tiempo real", "POST /monitorear": "Monitorear", "GET /alertas": "Alertas"},
        "docs": "/docs"
    }


@app.get("/ciudades")
async def obtener_ciudades():
    ciudades = [
        {"nombre": "Medellín", "departamento": "Antioquia", "slug": "medellin"}, {"nombre": "Caucasia", "departamento": "Antioquia", "slug": "caucasia"},
        {"nombre": "Jardín", "departamento": "Antioquia", "slug": "jardin"}, {"nombre": "Arboletes", "departamento": "Antioquia", "slug": "arboletes"},
        {"nombre": "Urrao", "departamento": "Antioquia", "slug": "urrao"}, {"nombre": "Ciudad Bolívar", "departamento": "Antioquia", "slug": "ciudad bolivar"},
        {"nombre": "Puerto Berrío", "departamento": "Antioquia", "slug": "puerto berrio"}, {"nombre": "Rionegro - Marinilla", "departamento": "Antioquia", "slug": "rionegro"},
        {"nombre": "Betulia", "departamento": "Antioquia", "slug": "betulia"}, {"nombre": "Andes", "departamento": "Antioquia", "slug": "andes"},
        {"nombre": "Giraldo", "departamento": "Antioquia", "slug": "giraldo"}, {"nombre": "Yarumal", "departamento": "Antioquia", "slug": "yarumal"},
        {"nombre": "Bolombolo", "departamento": "Antioquia", "slug": "bolombolo"}, {"nombre": "Concordia", "departamento": "Antioquia", "slug": "concordia"},
        {"nombre": "Tarazá", "departamento": "Antioquia", "slug": "taraza"}, {"nombre": "Caicedo", "departamento": "Antioquia", "slug": "caicedo"},
        {"nombre": "Barranquilla", "departamento": "Atlántico", "slug": "barranquilla"},
        {"nombre": "Cartagena", "departamento": "Bolívar", "slug": "cartagena"}, {"nombre": "Magangué", "departamento": "Bolívar", "slug": "magangue"},
        {"nombre": "San Onofre", "departamento": "Bolívar", "slug": "san onofre"}, {"nombre": "Carmen de Bolívar", "departamento": "Bolívar", "slug": "carmen de bolivar"},
        {"nombre": "Mompox", "departamento": "Bolívar", "slug": "mompox"}, {"nombre": "La Dorada", "departamento": "Caldas", "slug": "la dorada"},
        {"nombre": "Quibdó", "departamento": "Chocó", "slug": "quibdo"}, {"nombre": "Istmina", "departamento": "Chocó", "slug": "istmina"},
        {"nombre": "Condoto", "departamento": "Chocó", "slug": "condoto"}, {"nombre": "Tutunendo", "departamento": "Chocó", "slug": "tutunendo"},
        {"nombre": "Montería", "departamento": "Córdoba", "slug": "monteria"}, {"nombre": "Planeta Rica", "departamento": "Córdoba", "slug": "planeta rica"},
        {"nombre": "Lorica", "departamento": "Córdoba", "slug": "lorica"}, {"nombre": "Cereté", "departamento": "Córdoba", "slug": "cerete"},
        {"nombre": "La Apartada", "departamento": "Córdoba", "slug": "la apartada"}, {"nombre": "Chinú", "departamento": "Córdoba", "slug": "chinu"},
        {"nombre": "San Antero", "departamento": "Córdoba", "slug": "san antero"}, {"nombre": "Bogotá", "departamento": "Cundinamarca", "slug": "bogota"},
        {"nombre": "Maicao", "departamento": "La Guajira", "slug": "maicao"}, {"nombre": "Riohacha", "departamento": "La Guajira", "slug": "riohacha"},
        {"nombre": "Santa Marta", "departamento": "Magdalena", "slug": "santa marta"}, {"nombre": "Ciénaga", "departamento": "Magdalena", "slug": "cienaga"},
        {"nombre": "Sincelejo", "departamento": "Sucre", "slug": "sincelejo"}, {"nombre": "Coveñas", "departamento": "Sucre", "slug": "covenas"},
        {"nombre": "San Marcos", "departamento": "Sucre", "slug": "san marcos"}, {"nombre": "Tolú", "departamento": "Sucre", "slug": "tolu"},
        {"nombre": "Sahagún", "departamento": "Sucre", "slug": "sahagun"},
    ]
    return {"total": len(ciudades), "ciudades": sorted(ciudades, key=lambda x: x["nombre"]), "por_departamento": agrupar_por_departamento(ciudades)}


@app.get("/buscar")
async def endpoint_buscar(origen: str, destino: str, fecha: str, empresa: Optional[str] = None):
    fecha_redbus = convertir_fecha_a_redbus(fecha)
    resultado = await buscar_redbus_dinamico(origen, destino, fecha_redbus)
    resultados = resultado["resultados"]
    if empresa:
        resultados = [r for r in resultados if empresa.lower() in r["empresa"].lower()]
    resultados.sort(key=lambda x: x["hora_salida"])
    empresas_disponibles = list(set([r["empresa"] for r in resultados]))
    return {"exito": True, "origen": {"ciudad": origen.title(), "id": resultado["origen"]["id"], "nombre_completo": resultado["origen"]["name"]}, "destino": {"ciudad": destino.title(), "id": resultado["destino"]["id"], "nombre_completo": resultado["destino"]["name"]}, "fecha": fecha, "total_buses": len(resultados), "empresas_disponibles": sorted(empresas_disponibles), "horarios": resultados}


@app.get("/buscar-rapido-ochoa")
async def buscar_solo_rapido_ochoa(origen: str, destino: str, fecha: str):
    fecha_redbus = convertir_fecha_a_redbus(fecha)
    resultado = await buscar_redbus_dinamico(origen, destino, fecha_redbus)
    buses_ochoa = [bus for bus in resultado["resultados"] if "ochoa" in bus["empresa"].lower() or "rápido ochoa" in bus["empresa"].lower()]
    buses_ochoa.sort(key=lambda x: x["hora_salida"])
    return {"exito": True, "origen": {"ciudad": origen.title(), "id": resultado["origen"]["id"], "nombre_completo": resultado["origen"]["name"]}, "destino": {"ciudad": destino.title(), "id": resultado["destino"]["id"], "nombre_completo": resultado["destino"]["name"]}, "fecha": fecha, "empresa": "Rápido Ochoa", "total_buses": len(buses_ochoa), "horarios": buses_ochoa}


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
        return {"disponible": bus_encontrado["asientos_disponibles"] > 0, "asientos_disponibles": bus_encontrado["asientos_disponibles"], "asientos_totales": bus_encontrado["asientos_totales"], "precio": bus_encontrado["precio_total"], "estado": "DISPONIBLE" if bus_encontrado["asientos_disponibles"] > 10 else "POCOS ASIENTOS" if bus_encontrado["asientos_disponibles"] > 0 else "AGOTADO", "bus": bus_encontrado}
    else:
        return {"disponible": False, "mensaje": "Bus no encontrado"}


@app.get("/buscar-avanzado")
async def endpoint_buscar_avanzado(origen: str, destino: str, fecha: str, empresa: Optional[str] = None, precio_min: Optional[int] = None, precio_max: Optional[int] = None, hora_min: Optional[str] = None, hora_max: Optional[str] = None, asientos_min: Optional[int] = None, solo_ac: Optional[bool] = None, solo_cama: Optional[bool] = None, rating_min: Optional[float] = None, ordenar_por: Optional[str] = "hora"):
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
    elif ordenar_por == "rating":
        resultados.sort(key=lambda x: x["rating"], reverse=True)
    elif ordenar_por == "asientos":
        resultados.sort(key=lambda x: x["asientos_disponibles"], reverse=True)
    else:
        resultados.sort(key=lambda x: x["hora_salida"])
    empresas_disponibles = list(set([r["empresa"] for r in resultados]))
    if resultados:
        precio_promedio = sum(r["precio_total"] for r in resultados) / len(resultados)
        precio_mas_barato = min(r["precio_total"] for r in resultados)
        precio_mas_caro = max(r["precio_total"] for r in resultados)
    else:
        precio_promedio = precio_mas

        precio_promedio = precio_mas_barato = precio_mas_caro = 0
    return {"exito": True, "origen": {"ciudad": origen.title(), "id": resultado["origen"]["id"], "nombre_completo": resultado["origen"]["name"]}, "destino": {"ciudad": destino.title(), "id": resultado["destino"]["id"], "nombre_completo": resultado["destino"]["name"]}, "fecha": fecha, "filtros_aplicados": {"empresa": empresa, "precio_min": precio_min, "precio_max": precio_max, "hora_min": hora_min, "hora_max": hora_max, "asientos_min": asientos_min, "solo_ac": solo_ac, "solo_cama": solo_cama, "rating_min": rating_min, "ordenar_por": ordenar_por}, "estadisticas": {"total_resultados": len(resultados), "empresas_disponibles": sorted(empresas_disponibles), "precio_promedio": round(precio_promedio, 2), "precio_mas_barato": precio_mas_barato, "precio_mas_caro": precio_mas_caro}, "horarios": resultados}


@app.post("/monitorear")
async def agregar_monitoreo(origen: str, destino: str, fecha: str, horario: Optional[str] = None, empresa: Optional[str] = None):
    monitor = MonitorRuta(origen, destino, fecha, horario, empresa)
    rutas_monitoreadas[monitor.id] = monitor
    await revisar_disponibilidad(monitor)
    return {"exito": True, "mensaje": "Ruta agregada al monitoreo", "monitor": {"id": monitor.id, "origen": origen.title(), "destino": destino.title(), "fecha": fecha, "horario_especifico": horario, "empresa_especifica": empresa}, "configuracion": CONFIG_ALERTAS}


@app.get("/alertas")
async def obtener_alertas(nivel: Optional[str] = None, ultimas: Optional[int] = None):
    alertas = alertas_generadas.copy()
    if nivel:
        alertas = [a for a in alertas if a["nivel"] == nivel.upper()]
    alertas.sort(key=lambda x: x["timestamp"], reverse=True)
    if ultimas:
        alertas = alertas[:ultimas]
    return {"total_alertas": len(alertas), "alertas": alertas}

@app.get("/monitoreando")
async def ver_rutas_monitoreadas():
    monitores = []
    for monitor_id, monitor in rutas_monitoreadas.items():
        monitores.append({"id": monitor.id, "origen": monitor.origen, "destino": monitor.destino, "fecha": monitor.fecha, "horario_especifico": monitor.horario_especifico, "empresa_especifica": monitor.empresa_especifica, "activo": monitor.activo, "ultima_revision": monitor.ultima_revision.isoformat() if monitor.ultima_revision else None})
    return {"total_rutas_monitoreadas": len(monitores), "rutas": monitores, "configuracion": CONFIG_ALERTAS}


@app.delete("/monitorear/{monitor_id}")
async def detener_monitoreo(monitor_id: str):
    if monitor_id in rutas_monitoreadas:
        rutas_monitoreadas[monitor_id].activo = False
        return {"exito": True, "mensaje": f"Monitoreo detenido: {monitor_id}"}
    else:
        raise HTTPException(404, "Ruta no encontrada")


@app.put("/configurar-alertas")
async def configurar_alertas(umbral_critico: Optional[int] = None, umbral_advertencia: Optional[int] = None, intervalo_revision: Optional[int] = None):
    if umbral_critico is not None:
        CONFIG_ALERTAS["umbral_critico"] = umbral_critico
    if umbral_advertencia is not None:
        CONFIG_ALERTAS["umbral_advertencia"] = umbral_advertencia
    if intervalo_revision is not None:
        CONFIG_ALERTAS["intervalo_revision"] = intervalo_revision
    return {"exito": True, "mensaje": "Configuración actualizada", "configuracion_actual": CONFIG_ALERTAS}


@app.get("/estado/{monitor_id}")
async def ver_estado_actual(monitor_id: str):
    if monitor_id not in rutas_monitoreadas:
        raise HTTPException(404, "Ruta no encontrada")
    monitor = rutas_monitoreadas[monitor_id]
    await revisar_disponibilidad(monitor)
    alertas_ruta = [a for a in alertas_generadas if a["origen"] == monitor.origen and a["destino"] == monitor.destino and a["fecha"] == monitor.fecha]
    return {"monitor": {"id": monitor.id, "origen": monitor.origen, "destino": monitor.destino, "fecha": monitor.fecha, "ultima_revision": monitor.ultima_revision.isoformat() if monitor.ultima_revision else None}, "total_alertas": len(alertas_ruta), "alertas_recientes": alertas_ruta[-5:] if alertas_ruta else []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
