"""
Buscador de Buses Colombia v2.0
- Rápido Ochoa: API propia (one-api.rapidoochoa.com.co)
- Otras empresas: RedBus (rpw/api/searchResults)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Optional
from datetime import datetime
import asyncio
import time
from config import CONFIG_ALERTAS

app = FastAPI(
    title="Buscador de Buses Colombia",
    description="API con fuentes duales: Rápido Ochoa + RedBus",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

rutas_monitoreadas = {}
alertas_generadas = []
estado_anterior = {}

# ── Constantes ────────────────────────────────────────────────────────────────

OCHOA_TOKEN = "Token token=ac1d2715377e5d88e7fffe848034c0b1"
OCHOA_BASE  = "https://one-api.rapidoochoa.com.co/api/v2"
OCHOA_HEADERS = {
    "Authorization": OCHOA_TOKEN,
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://viaje.rapidoochoa.com.co",
    "Referer": "https://viaje.rapidoochoa.com.co/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

REDBUS_BASE = "https://www.redbus.co/rpw/api"
REDBUS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://www.redbus.co",
    "Referer": "https://www.redbus.co/",
}

# ── Mapa de ciudades con IDs para ambas APIs ──────────────────────────────────

CIUDADES = {
    "medellin": {
        "nombre": "Medellín",
        "departamento": "Antioquia",
        "redbus_id": "195160",
        "redbus_name": "Medellin (Ant) (Todos)",
        # OJO: Medellín tiene DOS terminales de Rápido Ochoa que cubren rutas
        # DISTINTAS (no son intercambiables). Dejamos "ochoa_slug" apuntando a
        # Terminal Norte por compatibilidad con el resto del codigo (RedBus,
        # /ciudades, etc.), pero la búsqueda real (buscar_ochoa) NO debe usar
        # solo este valor — debe consultar la lista MEDELLIN_TERMINALES de abajo
        # para tambien cubrir Terminal Sur (Chocó, Jardín, Andes, Urrao, ...).
        "ochoa_slug": "t-medellin-ad933da7-aca7-456a-a0e6-96e843785cd2-ochoa",
        "ochoa_name": "Medellín Terminal Norte",
    },
    # Entradas explícitas para que el catálogo /ciudades (y por ende el
    # autocompletado del panel de agentes) ofrezca cada terminal de Medellín
    # como opción propia. Útiles para que un agente busque/verifique la
    # cobertura de UNA terminal específica sin tener que escribir el nombre
    # completo (el datalist del panel ya autocompleta con estos "nombre").
    # OJO: estas claves NO reemplazan la entrada genérica "medellin" de arriba
    # (que sigue usando auto-detección de ambas terminales vía
    # MEDELLIN_TERMINALES); son atajos opcionales para apuntar a una sola.
    "medellin terminal norte": {
        "nombre": "Medellín Terminal Norte",
        "departamento": "Antioquia",
        "redbus_id": None,
        "redbus_name": None,
        "ochoa_slug": "t-medellin-ad933da7-aca7-456a-a0e6-96e843785cd2-ochoa",
        "ochoa_name": "Medellín Terminal Norte",
    },
    "medellin terminal sur": {
        "nombre": "Medellín Terminal Sur",
        "departamento": "Antioquia",
        "redbus_id": None,
        "redbus_name": None,
        "ochoa_slug": "t-medellin-3e6b672a-2b2b-409c-b8d6-3487e087e639-ochoa",
        "ochoa_name": "Medellín Terminal Sur",
    },
    "barranquilla": {
        "nombre": "Barranquilla",
        "departamento": "Atlántico",
        "redbus_id": "195179",
        "redbus_name": "Barranquilla (Atl) (Todos)",
        "ochoa_slug": "t-barranquilla-03cee54d-a938-4d67-93d7-b4ac9c1aa660-ochoa",
        "ochoa_name": "Barranquilla",
    },
    "monteria": {
        "nombre": "Montería",
        "departamento": "Córdoba",
        "redbus_id": "195200",
        "redbus_name": "Monteria (Cor) (Todos)",
        "ochoa_slug": "t-monteria-84c13da6-23a7-4cd2-9197-c4fd4deeb6ad-ochoa",
        "ochoa_name": "Montería",
    },
    "cartagena": {
        "nombre": "Cartagena",
        "departamento": "Bolívar",
        "redbus_id": "195181",
        "redbus_name": "Cartagena (Bol) (Todos)",
        "ochoa_slug": "t-cartagena-5e13cd74-efd9-427f-b39e-3de02025d338-ochoa",
        "ochoa_name": "Cartagena",
    },
    "sincelejo": {
        "nombre": "Sincelejo",
        "departamento": "Sucre",
        "redbus_id": "195243",
        "redbus_name": "Sincelejo (Suc) (Todos)",
        "ochoa_slug": "t-sincelejo-ochoa",
        "ochoa_name": "Sincelejo",
    },
    "bogota": {
        "nombre": "Bogotá",
        "departamento": "Cundinamarca",
        "redbus_id": "195201",
        "redbus_name": "Bogota (D.C) (Todos)",
        "ochoa_slug": "t-bogota-26eddda1-587e-47ac-856a-73ceed0fae96-ochoa",
        "ochoa_name": "Bogotá Terminal Salitre",
    },
    "santa marta": {
        "nombre": "Santa Marta",
        "departamento": "Magdalena",
        "redbus_id": "195215",
        "redbus_name": "Santa Marta (Mag) (Todos)",
        "ochoa_slug": "t-santa-marta-ochoa",
        "ochoa_name": "Santa Marta",
    },
    "caucasia": {
        "nombre": "Caucasia",
        "departamento": "Antioquia",
        "redbus_id": "195150",
        "redbus_name": "Caucasia (Ant) (Todos)",
        "ochoa_slug": "t-caucasia-a90bf704-c4fe-4c6a-8e49-505d8e33a67d-ochoa",
        "ochoa_name": "Caucasia",
    },
    "planeta rica": {
        "nombre": "Planeta Rica",
        "departamento": "Córdoba",
        "redbus_id": "195548",
        "redbus_name": "Planeta Rica (Cor) (Todos)",
        "ochoa_slug": "t-planeta-rica-617f0bd3-5b0f-4d9e-ab86-cbe6e54fc1d8-ochoa",
        "ochoa_name": "Planeta Rica",
    },
    "riohacha": {
        "nombre": "Riohacha",
        "departamento": "La Guajira",
        "redbus_id": "195204",
        "redbus_name": "Riohacha (Guaj) (Todos)",
        "ochoa_slug": "t-riohacha-ochoa",
        "ochoa_name": "Riohacha",
    },
    "maicao": {
        "nombre": "Maicao",
        "departamento": "La Guajira",
        "redbus_id": "195205",
        "redbus_name": "Maicao (Guaj) (Todos)",
        "ochoa_slug": "t-maicao-06618764-7308-49a5-99e8-6c43b951c755-ochoa",
        "ochoa_name": "Maicao",
    },
    "quibdo": {
        "nombre": "Quibdó",
        "departamento": "Chocó",
        "redbus_id": "195175",
        "redbus_name": "Quibdo (Cho) (Todos)",
        "ochoa_slug": "t-quibdo-ochoa",
        "ochoa_name": "Quibdó",
    },
    "tolu": {
        "nombre": "Tolú",
        "departamento": "Sucre",
        "redbus_id": "196394",
        "redbus_name": "Tolu (Suc) (Todos)",
        "ochoa_slug": "t-tolu-ochoa",
        "ochoa_name": "Tolú",
    },
    "covenas": {
        "nombre": "Coveñas",
        "departamento": "Sucre",
        "redbus_id": "196179",
        "redbus_name": "Covenas (Suc) (Todos)",
        "ochoa_slug": "t-covenas-bdd75504-d89c-41af-8bf2-e88db378e24f-ochoa",
        "ochoa_name": "Coveñas",
    },
    "lorica": {
        "nombre": "Lorica",
        "departamento": "Córdoba",
        "redbus_id": "194924",
        "redbus_name": "Lorica (Cor) (Todos)",
        "ochoa_slug": "t-lorica-ba275cb0-353e-498b-9e44-418598d49e10-ochoa",
        "ochoa_name": "Lorica",
    },
    "cerete": {
        "nombre": "Cereté",
        "departamento": "Córdoba",
        "redbus_id": "196158",
        "redbus_name": "Cerete (Cor) (Todos)",
        "ochoa_slug": "t-cerete-61e41806-ecc9-4ad5-8d69-99e071317d72-ochoa",
        "ochoa_name": "Cereté",
    },
    "la apartada": {
        "nombre": "La Apartada",
        "departamento": "Córdoba",
        "redbus_id": "195547",
        "redbus_name": "La Apartada (Cor) (Todos)",
        "ochoa_slug": "t-la-apartada-abaf6891-9896-4fed-bdf0-05fabf2c4a46-ochoa",
        "ochoa_name": "La Apartada",
    },
    "chinu": {
        "nombre": "Chinú",
        "departamento": "Córdoba",
        "redbus_id": "195541",
        "redbus_name": "Chinu (Cor) (Todos)",
        "ochoa_slug": "t-chinu-6a189f68-de46-41a6-b095-351e9c66ff76-ochoa",
        "ochoa_name": "Chinú",
    },
    "sahagun": {
        "nombre": "Sahagún",
        "departamento": "Córdoba",
        "redbus_id": "195550",
        "redbus_name": "Sahagun (Cor) (Todos)",
        "ochoa_slug": "t-sahagun-ochoa",
        "ochoa_name": "Sahagún",
    },
    "magangue": {
        "nombre": "Magangué",
        "departamento": "Bolívar",
        "redbus_id": "196300",
        "redbus_name": "Magangue (Bol) (Todos)",
        "ochoa_slug": "t-magangue-4ffd627c-331c-4ae3-b540-beb22f7d128e-ochoa",
        "ochoa_name": "Magangue",
    },
    "carmen de bolivar": {
        "nombre": "Carmen de Bolívar",
        "departamento": "Bolívar",
        "redbus_id": "195800",
        "redbus_name": "Carmen De Bolivar (Bol) (Todos)",
        "ochoa_slug": "t-carmen-de-bolivar-85e23a0a-f7bf-4de7-a985-2d585b69a379-ochoa",
        "ochoa_name": "Carmen de Bolívar",
    },
    "cienaga": {
        "nombre": "Ciénaga",
        "departamento": "Magdalena",
        "redbus_id": "195553",
        "redbus_name": "Cienaga (Mag) (Todos)",
        "ochoa_slug": "t-cienaga-ff869e21-0dee-4395-bd6d-06fdc437338e-ochoa",
        "ochoa_name": "Ciénaga",
    },
    "la dorada": {
        "nombre": "La Dorada",
        "departamento": "Caldas",
        "redbus_id": "195187",
        "redbus_name": "La Dorada (Cal) (Todos)",
        "ochoa_slug": "t-la-dorada-982bc6eb-ae93-4f8f-b385-909f34698c13-ochoa",
        "ochoa_name": "La Dorada",
    },
    "puerto berrio": {
        "nombre": "Puerto Berrío",
        "departamento": "Antioquia",
        "redbus_id": "196351",
        "redbus_name": "Puerto Berrio (Ant) (Todos)",
        "ochoa_slug": "t-puerto-berrio-0f0d8340-3724-4d92-bbb8-0149c9beb914-ochoa",
        "ochoa_name": "Puerto Berrio",
    },
    "caucasia": {
        "nombre": "Caucasia",
        "departamento": "Antioquia",
        "redbus_id": "195150",
        "redbus_name": "Caucasia (Ant) (Todos)",
        "ochoa_slug": "t-caucasia-a90bf704-c4fe-4c6a-8e49-505d8e33a67d-ochoa",
        "ochoa_name": "Caucasia",
    },
    "jardin": {
        "nombre": "Jardín",
        "departamento": "Antioquia",
        "redbus_id": "195158",
        "redbus_name": "Jardin (Ant) (Todos)",
        "ochoa_slug": "t-jardin-a056b1a2-384a-47fd-ad24-dcce1d92e810-ochoa",
        "ochoa_name": "Jardín",
    },
    "urrao": {
        "nombre": "Urrao",
        "departamento": "Antioquia",
        "redbus_id": "195175",
        "redbus_name": "Urrao (Ant) (Todos)",
        "ochoa_slug": "t-urrao-ochoa",
        "ochoa_name": "Urrao",
    },
    "ciudad bolivar": {
        "nombre": "Ciudad Bolívar",
        "departamento": "Antioquia",
        "redbus_id": "195153",
        "redbus_name": "Ciudad Bolivar (Ant) (Todos)",
        "ochoa_slug": "t-ciudad-bolivar-4415bc09-8da1-4b06-b5fd-e6d1c919898c-ochoa",
        "ochoa_name": "Ciudad Bolívar",
    },
    "yarumal": {
        "nombre": "Yarumal",
        "departamento": "Antioquia",
        "redbus_id": "195545",
        "redbus_name": "Yarumal (Ant) (Todos)",
        "ochoa_slug": "t-yarumal-ochoa",
        "ochoa_name": "Yarumal",
    },
    "taraza": {
        "nombre": "Tarazá",
        "departamento": "Antioquia",
        "redbus_id": "195540",
        "redbus_name": "Taraza (Ant) (Todos)",
        "ochoa_slug": "t-taraza-ochoa",
        "ochoa_name": "Tarazá",
    },
    "caicedo": {
        "nombre": "Caicedo",
        "departamento": "Antioquia",
        "redbus_id": "195491",
        "redbus_name": "Caicedo (Ant) (Todos)",
        "ochoa_slug": "t-caicedo-30d35bdf-1a39-4a41-be69-c69810b9d1f0-ochoa",
        "ochoa_name": "Caicedo",
    },
    "istmina": {
        "nombre": "Istmina",
        "departamento": "Chocó",
        "redbus_id": "196805",
        "redbus_name": "Istmina (Cho) (Todos)",
        "ochoa_slug": "t-istmina-54aa1e24-8a92-484a-aedc-59be05a474e8-ochoa",
        "ochoa_name": "Istmina",
    },
    "condoto": {
        "nombre": "Condoto",
        "departamento": "Chocó",
        "redbus_id": "195199",
        "redbus_name": "Condoto (Cho) (Todos)",
        "ochoa_slug": "t-condoto-b29b0bb3-d8c0-4885-9609-899c786468c1-ochoa",
        "ochoa_name": "Condoto",
    },
    "tutunendo": {
        "nombre": "Tutunendo",
        "departamento": "Chocó",
        "redbus_id": "195531",
        "redbus_name": "Tutunendo (Cho) (Todos)",
        "ochoa_slug": "t-tutunendo-ochoa",
        "ochoa_name": "Tutunendo",
    },
    "rionegro": {
        "nombre": "Rionegro - Marinilla",
        "departamento": "Antioquia",
        "redbus_id": "202962",
        "redbus_name": "Rionegro (Ant) (Todos)",
        "ochoa_slug": "t-rionegro-ochoa",
        "ochoa_name": "Rionegro - Marinilla",
    },
    "san marcos": {
        "nombre": "San Marcos",
        "departamento": "Sucre",
        "redbus_id": "195565",
        "redbus_name": "San Marcos (Suc) (Todos)",
        "ochoa_slug": "t-san-marcos-ochoa",
        "ochoa_name": "San Marcos",
    },
    "san antero": {
        "nombre": "San Antero",
        "departamento": "Córdoba",
        "redbus_id": "196364",
        "redbus_name": "San Antero (Cor) (Todos)",
        "ochoa_slug": "t-san-antero-ochoa",
        "ochoa_name": "San Antero",
    },
    "san onofre": {
        "nombre": "San Onofre",
        "departamento": "Bolívar",
        "redbus_id": "195566",
        "redbus_name": "San Onofre (Suc) (Todos)",
        "ochoa_slug": "t-san-onofre-ochoa",
        "ochoa_name": "San Onofre",
    },
    "arboletes": {
        "nombre": "Arboletes",
        "departamento": "Antioquia",
        "redbus_id": "195102",
        "redbus_name": "Arboletes (Ant) (Todos)",
        "ochoa_slug": "t-arboletes-42417357-bc6f-4ba4-9f86-89ab986a6075-ochoa",
        "ochoa_name": "Arboletes",
    },
    "betulia": {
        "nombre": "Betulia",
        "departamento": "Antioquia",
        "redbus_id": "195489",
        "redbus_name": "Betulia (Ant) (Todos)",
        "ochoa_slug": "t-betulia-983d843e-2025-42b1-8510-1f49ce3461bd-ochoa",
        "ochoa_name": "Betulia",
    },
    "concordia": {
        "nombre": "Concordia",
        "departamento": "Antioquia",
        "redbus_id": "195500",
        "redbus_name": "Concordia (Ant) (Todos)",
        "ochoa_slug": "t-concordia-8b2b560e-0b04-4e10-9507-5ba3808ef1eb-ochoa",
        "ochoa_name": "Concordia",
    },
    "bolombolo": {
        "nombre": "Bolombolo",
        "departamento": "Antioquia",
        "redbus_id": "195490",
        "redbus_name": "Bolombolo (Ant) (Todos)",
        "ochoa_slug": "t-bolombolo-92fdca4d-e5ea-48aa-9844-17c3084458ab-ochoa",
        "ochoa_name": "Bolombolo",
    },
    "giraldo": {
        "nombre": "Giraldo",
        "departamento": "Antioquia",
        "redbus_id": "195157",
        "redbus_name": "Giraldo (Ant) (Todos)",
        "ochoa_slug": "t-giraldo-de4431c7-3153-49a0-b1ae-81f99061667e-ochoa",
        "ochoa_name": "Giraldo",
    },
    "andes": {
        "nombre": "Andes",
        "departamento": "Antioquia",
        "redbus_id": "195488",
        "redbus_name": "Andes (Ant) (Todos)",
        "ochoa_slug": "t-andes-0b98aae3-b325-43cc-9cd8-b4628c070f18-ochoa",
        "ochoa_name": "Andes",
    },
    "mompox": {
        "nombre": "Mompox",
        "departamento": "Bolívar",
        "redbus_id": "195833",
        "redbus_name": "Mompox (Bol) (Todos)",
        "ochoa_slug": "t-mompox-mompox-ochoa",
        "ochoa_name": "Mompox",
    },
    "valledupar": {
        "nombre": "Valledupar",
        "departamento": "Cesar",
        "redbus_id": None,
        "redbus_name": None,
        "ochoa_slug": "t-valledupar-ochoa",
        "ochoa_name": "Valledupar",
    },
    "facatativa": {
        "nombre": "Facatativá",
        "departamento": "Cundinamarca",
        "redbus_id": None,
        "redbus_name": None,
        "ochoa_slug": "t-facatativa-1f0b4224-e083-4a0c-bb23-006788d9f2fe-ochoa",
        "ochoa_name": "Facatativa",
    },
}

# ── Terminales de Medellín (Rápido Ochoa) ─────────────────────────────────────
# Medellín NO es un solo punto de salida: Rápido Ochoa opera desde DOS terminales
# que cubren rutas distintas y no intercambiables:
#   - Terminal Norte: cubre la mayoría de las rutas "grandes" (Bogotá, Caucasia,
#     Montería, Cartagena, etc.)
#   - Terminal Sur: cubre rutas hacia el suroeste antioqueño y Chocó (Quibdó,
#     Istmina, Cóndoto, Tutunendo, El Siete, Jardín, Andes, Urrao, Concordia,
#     Caicedo, Betulia, Bolombolo, Ciudad Bolívar, etc.)
#
# Antes, "medellin" solo apuntaba al slug de Terminal Norte, así que cualquier
# búsqueda hacia un destino que SOLO sale de Terminal Sur devolvía "no hay viajes"
# (falso negativo: la ruta sí existe, solo que Rápido Ochoa la opera desde la otra
# terminal). buscar_ochoa ahora prueba ambas terminales cuando la ciudad es
# Medellín, y usa la que sí tenga viajes disponibles.
MEDELLIN_TERMINALES = [
    {"slug": "t-medellin-ad933da7-aca7-456a-a0e6-96e843785cd2-ochoa", "nombre": "Medellín Terminal Norte"},
    {"slug": "t-medellin-3e6b672a-2b2b-409c-b8d6-3487e087e639-ochoa", "nombre": "Medellín Terminal Sur"},
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def convertir_fecha_redbus(fecha_input: str) -> str:
    meses = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
              7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            f = datetime.strptime(fecha_input, fmt)
            return f"{f.day:02d}-{meses[f.month]}-{f.year}"
        except:
            continue
    raise HTTPException(400, "Formato de fecha inválido. Usa YYYY-MM-DD")

def convertir_fecha_ochoa(fecha_input: str) -> str:
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            f = datetime.strptime(fecha_input, fmt)
            return f"{f.day:02d}-{f.month:02d}-{f.year}"
        except:
            continue
    raise HTTPException(400, "Formato de fecha inválido. Usa YYYY-MM-DD")

def buscar_ciudad(nombre: str) -> Optional[Dict]:
    key = nombre.lower().strip()
    return CIUDADES.get(key)

def obtener_terminales_ochoa(ciudad: Dict) -> list:
    """Lista de terminales [{slug, nombre}] a probar para una ciudad en Rápido Ochoa.

    Para Medellín devolvemos AMBAS terminales (Norte y Sur) porque cubren rutas
    distintas — ver el comentario junto a MEDELLIN_TERMINALES. Para cualquier
    otra ciudad devolvemos su único slug de siempre (comportamiento sin cambios)."""
    if ciudad.get("nombre") == "Medellín":
        return MEDELLIN_TERMINALES
    slug = ciudad.get("ochoa_slug")
    if not slug:
        return []
    return [{"slug": slug, "nombre": ciudad.get("ochoa_name") or ciudad["nombre"]}]

# ── Fuente Rápido Ochoa ───────────────────────────────────────────────────────

async def _buscar_trips_ochoa(slug_origen: str, slug_destino: str, fecha_ochoa: str):
    """Ejecuta UNA búsqueda (origen→destino ya resueltos a slugs) y devuelve
    (search_id, trips). Aislado en su propia función para poder probar varias
    combinaciones de terminales (ver buscar_ochoa) sin repetir el polling."""
    r1 = await client.post(f"{OCHOA_BASE}/search", json={
        "origin": slug_origen,
        "destination": slug_destino,
        "date": fecha_ochoa,
        "passengers": ["adult"],
        "round": False,
        "way": "oneway"
    }, headers=OCHOA_HEADERS)
    r1.raise_for_status()
    search_id = r1.json()["search"]["id"]

    trips = []
    for _ in range(5):
        await asyncio.sleep(2)
        r2 = await client.get(
            f"{OCHOA_BASE}/search/{search_id}?type=bus",
            headers=OCHOA_HEADERS
        )
        data = r2.json()
        trips = data.get("trips", [])
        if trips or data.get("state") == "finished":
            break
    return search_id, trips

def _formatear_trips_ochoa(trips: list, terminal_o: Dict, terminal_d: Dict) -> list:
    resultados = []
    for t in trips:
        dep = t.get("departure", "")
        arr = t.get("arrival", "")
        resultados.append({
            "empresa": "Rápido Ochoa",
            "tipo_bus": t.get("service", ""),
            "servicio": t.get("service", ""),
            "hora_salida": dep.split("T")[1][:5] if "T" in dep else dep,
            "hora_llegada": arr.split("T")[1][:5] if "T" in arr else arr,
            "fecha_salida": dep,
            "fecha_llegada": arr,
            "duracion_minutos": t.get("duration", 0),
            "duracion_horas": round(t.get("duration", 0) / 60, 1),
            "precio": t.get("pricing", {}).get("office_price", 0),
            "precio_total": t.get("pricing", {}).get("total", 0),
            "precio_descuento": t.get("pricing", {}).get("total", 0),
            "tarifa_servicio": 0,
            "moneda": "COP",
            "asientos_disponibles": t.get("availability", 0),
            "asientos_totales": t.get("capacity", 0),
            "es_ac": True,
            "es_cama": False,
            "rating": 0,
            "num_reviews": "0",
            "agotado": t.get("availability", 0) == 0,
            "trip_id": t.get("id"),
            "fuente": "rapido_ochoa",
            # Terminal real de salida/llegada usada para encontrar este viaje —
            # util quando Medellín tiene mas de una terminal (Norte/Sur) y el
            # llamador (chatbot/agente) necesita saber de cual exactamente sale.
            "terminal_salida": terminal_o["nombre"],
            "terminal_llegada": terminal_d["nombre"],
        })
    return resultados

async def buscar_ochoa(origen: str, destino: str, fecha: str) -> Dict:
    ciudad_o = buscar_ciudad(origen)
    ciudad_d = buscar_ciudad(destino)
    if not ciudad_o:
        raise HTTPException(404, f"Ciudad no encontrada: {origen}")
    if not ciudad_d:
        raise HTTPException(404, f"Ciudad no encontrada: {destino}")

    terminales_o = obtener_terminales_ochoa(ciudad_o)
    terminales_d = obtener_terminales_ochoa(ciudad_d)
    if not terminales_o or not terminales_d:
        raise HTTPException(404, f"Ruta no disponible en Rápido Ochoa")

    fecha_ochoa = convertir_fecha_ochoa(fecha)

    # Probamos cada combinación terminal-origen × terminal-destino (normalmente
    # solo hay 1 de cada lado; para Medellín hay 2, así que como máximo son 4
    # combinaciones) y nos quedamos con la PRIMERA que sí devuelva viajes. Así
    # cubrimos el caso real: Medellín → Quibdó solo existe desde Terminal Sur,
    # mientras que Medellín → Bogotá solo existe desde Terminal Norte — antes,
    # al estar "medellin" fijo a Terminal Norte, la primera ruta daba un falso
    # "no hay viajes" aunque la empresa sí la opera.
    search_id = None
    resultados = []
    terminal_o_usada = terminales_o[0]
    terminal_d_usada = terminales_d[0]

    for t_o in terminales_o:
        for t_d in terminales_d:
            if t_o["slug"] == t_d["slug"]:
                continue  # origen y destino no pueden resolver a la misma terminal
            try:
                sid, trips = await _buscar_trips_ochoa(t_o["slug"], t_d["slug"], fecha_ochoa)
            except httpx.HTTPStatusError:
                continue
            if search_id is None:
                search_id = sid  # guardamos el primero como referencia, por si todas quedan vacias
            if trips:
                search_id = sid
                terminal_o_usada, terminal_d_usada = t_o, t_d
                resultados = _formatear_trips_ochoa(trips, t_o, t_d)
                break
        if resultados:
            break

    return {
        "origen": {"ciudad": ciudad_o["nombre"], "id": terminal_o_usada["slug"], "terminal": terminal_o_usada["nombre"]},
        "destino": {"ciudad": ciudad_d["nombre"], "id": terminal_d_usada["slug"], "terminal": terminal_d_usada["nombre"]},
        "search_id": search_id,
        "resultados": resultados,
    }

# ── Fuente RedBus ─────────────────────────────────────────────────────────────

REDBUS_BODY_BASE = {
    "appliedFilterCount": 0,
    "onlyShow": [], "dt": [], "SeaterType": [], "AcType": [],
    "travelsList": [], "amtList": [], "at": [], "bcf": [],
    "bpIdentifier": [], "bpKeys": [], "bpList": [],
    "dpIdentifier": [], "dpKeys": [], "dpList": [],
    "RouteIds": [], "CampaignFilter": [], "opBusTypeFilterList": [],
    "persuasionList": [], "preRouteFilters": None,
    "priceRange": [], "streaksFilter": []
}

async def buscar_redbus(origen: str, destino: str, fecha: str, empresa: Optional[str] = None) -> Dict:
    ciudad_o = buscar_ciudad(origen)
    ciudad_d = buscar_ciudad(destino)

    # Fallback a búsqueda dinámica si no está en el mapa
    if not ciudad_o or not ciudad_o.get("redbus_id"):
        raise HTTPException(404, f"Ciudad no disponible en RedBus: {origen}")
    if not ciudad_d or not ciudad_d.get("redbus_id"):
        raise HTTPException(404, f"Ciudad no disponible en RedBus: {destino}")

    fecha_rb = convertir_fecha_redbus(fecha)
    todos = []
    offset = 0

    for _ in range(5):
        r = await client.post(
            f"{REDBUS_BASE}/searchResults",
            params={
                "fromCity": ciudad_o["redbus_id"],
                "toCity": ciudad_d["redbus_id"],
                "DOJ": fecha_rb,
                "limit": "100", "offset": str(offset),
                "meta": "true", "groupId": "0", "sectionId": "0",
                "sort": "0", "sortOrder": "0",
                "from": "initialLoad" if offset == 0 else "pagination",
                "getUuid": "true", "bT": "1",
                "clearLMBFilter": "undefined", "isFilterApplied": "false",
            },
            json=REDBUS_BODY_BASE,
            headers=REDBUS_HEADERS,
        )
        r.raise_for_status()
        data = r.json()
        inventories = data.get("data", {}).get("inventories", [])
        total = data.get("data", {}).get("metaData", {}).get("totalCount", 0)
        if not inventories:
            break

        for bus in inventories:
            dep = bus.get("departureTime", "")
            arr = bus.get("arrivalTime", "")
            todos.append({
                "empresa": bus.get("travelsName", ""),
                "tipo_bus": bus.get("busType", ""),
                "servicio": bus.get("serviceName", ""),
                "hora_salida": dep.split(" ")[1] if dep else "",
                "hora_llegada": arr.split(" ")[1] if arr else "",
                "fecha_salida": dep,
                "fecha_llegada": arr,
                "duracion_minutos": bus.get("journeyDurationMin", 0),
                "duracion_horas": round(bus.get("journeyDurationMin", 0) / 60, 1),
                "precio": bus.get("fareList", [0])[0] if bus.get("fareList") else 0,
                "precio_total": (bus.get("fareList", [0])[0] + bus.get("convenienceFee", 0)) if bus.get("fareList") else 0,
                "tarifa_servicio": bus.get("convenienceFee", 0),
                "moneda": "COP",
                "asientos_disponibles": bus.get("availableSeats", 0),
                "asientos_totales": bus.get("totalSeats", 0),
                "punto_embarque": bus.get("standardBpName", ""),
                "punto_desembarque": bus.get("standardDpName", ""),
                "es_ac": bus.get("isAc", False),
                "es_cama": bus.get("isSleeper", False),
                "rating": bus.get("totalRatings", 0),
                "num_reviews": bus.get("numberOfReviews", "0"),
                "agotado": bus.get("isSoldOut", False),
                "route_id": bus.get("routeId"),
                "operator_id": bus.get("operatorId"),
                "fuente": "redbus",
            })

        if len(todos) >= total:
            break
        offset += 100

    if empresa:
        todos = [b for b in todos if empresa.lower() in b["empresa"].lower()]

    return {
        "origen": {"ciudad": ciudad_o["nombre"], "id": ciudad_o["redbus_id"], "nombre_completo": ciudad_o["redbus_name"]},
        "destino": {"ciudad": ciudad_d["nombre"], "id": ciudad_d["redbus_id"], "nombre_completo": ciudad_d["redbus_name"]},
        "resultados": todos,
    }

# ── Sillas Rápido Ochoa ───────────────────────────────────────────────────────

async def obtener_sillas_ochoa(trip_id: str) -> Dict:
    r1 = await client.post(
        f"{OCHOA_BASE}/trips/{trip_id}/details_requests",
        json={}, headers=OCHOA_HEADERS
    )
    r1.raise_for_status()
    dr_id = r1.json()["id"]
    await asyncio.sleep(2)

    r2 = await client.get(
        f"{OCHOA_BASE}/trips/{trip_id}/details_requests/{dr_id}",
        headers=OCHOA_HEADERS
    )
    r2.raise_for_status()
    bus_layout = r2.json().get("bus", [[]])[0]

    disponibles = sorted(
        [s["number"] for f in bus_layout for s in f if s.get("category") == "seat" and not s["occupied"] and not s["sold"]],
        key=int
    )
    ocupadas = sorted(
        [s["number"] for f in bus_layout for s in f if s.get("category") == "seat" and (s["occupied"] or s["sold"])],
        key=int
    )
    return {
        "total": len(disponibles) + len(ocupadas),
        "num_disponibles": len(disponibles),
        "num_ocupadas": len(ocupadas),
        "disponibles": disponibles,
        "ocupadas": ocupadas,
    }

# ── Sillas RedBus ─────────────────────────────────────────────────────────────

async def obtener_sillas_redbus(route_id: int, operator_id: int, fecha: str,
                                from_city_name: str, to_city_name: str) -> Dict:
    fecha_rb = convertir_fecha_redbus(fecha)
    r = await client.get(
        f"{REDBUS_BASE}/seatLayout",
        params={
            "doj": fecha_rb, "routeId": str(route_id), "oid": str(operator_id),
            "seniorCitizen": "", "deal": "",
            "toCityName": to_city_name, "fromCityName": from_city_name,
            "bT": "1", "removeStaleInvFromSRP": "true",
        },
        headers=REDBUS_HEADERS
    )
    r.raise_for_status()
    services = r.json().get("services", [])
    if not services:
        return {"disponibles": [], "ocupadas": [], "total": 0, "num_disponibles": 0, "num_ocupadas": 0}

    seatlist = services[0].get("seatlist", [])
    disponibles = sorted([s["Id"] for s in seatlist if s["IsAvailable"]], key=int)
    ocupadas = sorted([s["Id"] for s in seatlist if not s["IsAvailable"]], key=int)
    return {
        "total": len(seatlist),
        "num_disponibles": len(disponibles),
        "num_ocupadas": len(ocupadas),
        "disponibles": disponibles,
        "ocupadas": ocupadas,
    }

# ── Sistema de alertas ────────────────────────────────────────────────────────

class MonitorRuta:
    def __init__(self, origen, destino, fecha, horario=None, empresa=None, fuente="rapido_ochoa"):
        self.origen = origen
        self.destino = destino
        self.fecha = fecha
        self.horario = horario
        self.empresa = empresa
        self.fuente = fuente
        self.activo = True
        self.ultima_revision = None
        self.id = f"{origen}_{destino}_{fecha}_{horario or 'todos'}_{fuente}"

async def revisar_disponibilidad(monitor: MonitorRuta):
    try:
        if monitor.fuente == "rapido_ochoa":
            resultado = await buscar_ochoa(monitor.origen, monitor.destino, monitor.fecha)
        else:
            resultado = await buscar_redbus(monitor.origen, monitor.destino, monitor.fecha, monitor.empresa)

        horarios = resultado["resultados"]
        if monitor.horario:
            horarios = [h for h in horarios if h["hora_salida"].startswith(monitor.horario)]
        if monitor.empresa and monitor.fuente != "rapido_ochoa":
            horarios = [h for h in horarios if monitor.empresa.lower() in h["empresa"].lower()]

        for h in horarios:
            generar_alerta(monitor, h)
        monitor.ultima_revision = datetime.now()
    except Exception as e:
        print(f"Error monitor {monitor.id}: {e}")

def generar_alerta(monitor: MonitorRuta, horario: Dict):
    asientos = horario["asientos_disponibles"]
    key = f"{monitor.id}_{horario['hora_salida']}_{horario['empresa']}"
    prev = estado_anterior.get(key, {}).get("asientos")
    estado_anterior[key] = {"asientos": asientos, "timestamp": datetime.now()}

    alerta = None
    if asientos == 0 and prev != 0:
        alerta = {"tipo": "AGOTADO", "nivel": "CRITICO",
                  "mensaje": f"🚨 SIN PUESTOS: {horario['empresa']} - {horario['hora_salida']}"}
    elif 0 < asientos <= CONFIG_ALERTAS["umbral_critico"] and (prev is None or prev > CONFIG_ALERTAS["umbral_critico"]):
        alerta = {"tipo": "CRITICO", "nivel": "ALTO",
                  "mensaje": f"⚠️ SOLO {asientos} PUESTOS: {horario['empresa']} - {horario['hora_salida']}"}
    elif CONFIG_ALERTAS["umbral_critico"] < asientos <= CONFIG_ALERTAS["umbral_advertencia"] and (prev is None or prev > CONFIG_ALERTAS["umbral_advertencia"]):
        alerta = {"tipo": "ADVERTENCIA", "nivel": "MEDIO",
                  "mensaje": f"⚡ {asientos} puestos: {horario['empresa']} - {horario['hora_salida']}"}

    if alerta:
        alerta.update({
            "origen": monitor.origen, "destino": monitor.destino,
            "fecha": monitor.fecha, "empresa": horario["empresa"],
            "hora_salida": horario["hora_salida"],
            "asientos_disponibles": asientos,
            "precio": horario["precio_total"],
            "timestamp": datetime.now().isoformat(),
        })
        alertas_generadas.append(alerta)
        print(f"🔔 {alerta['mensaje']}")

async def monitor_loop():
    while True:
        try:
            for monitor in list(rutas_monitoreadas.values()):
                if monitor.activo:
                    await revisar_disponibilidad(monitor)
            await asyncio.sleep(CONFIG_ALERTAS["intervalo_revision"])
        except Exception as e:
            print(f"Error monitor loop: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_loop())
    print("🚀 Buscador de Buses v2.0 iniciado")

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "nombre": "🚌 Buscador de Buses Colombia v2.0",
        "version": "2.0.0",
        "fuentes": {
            "rapido_ochoa": "API oficial de Rápido Ochoa",
            "redbus": "RedBus Colombia (todas las empresas)",
        },
        "endpoints": {
            "GET /buscar-rapido-ochoa": "Solo Rápido Ochoa (API oficial)",
            "GET /buscar": "Todas las empresas (RedBus)",
            "GET /buscar-avanzado": "RedBus con filtros",
            "GET /sillas/ochoa/{trip_id}": "Sillas por trip_id de Ochoa",
            "GET /sillas/redbus": "Sillas por route_id de RedBus",
            "GET /ciudades": "Ciudades disponibles",
            "GET /health": "Estado del servicio",
        },
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "version": "2.0.0"}

@app.get("/ciudades")
async def obtener_ciudades():
    lista = [
        {"slug": k, "nombre": v["nombre"], "departamento": v["departamento"],
         "disponible_ochoa": bool(v.get("ochoa_slug")),
         "disponible_redbus": bool(v.get("redbus_id"))}
        for k, v in CIUDADES.items()
    ]
    return {"total": len(lista), "ciudades": sorted(lista, key=lambda x: x["nombre"])}

@app.get("/buscar-rapido-ochoa")
async def endpoint_ochoa(origen: str, destino: str, fecha: str):
    """Busca buses de Rápido Ochoa usando su API oficial."""
    resultado = await buscar_ochoa(origen, destino, fecha)
    buses = sorted(resultado["resultados"], key=lambda x: x["hora_salida"])
    return {
        "exito": True,
        "fuente": "rapido_ochoa",
        "origen": resultado["origen"],
        "destino": resultado["destino"],
        "fecha": fecha,
        "empresa": "Rápido Ochoa",
        "total_buses": len(buses),
        "horarios": buses,
    }

@app.get("/buscar")
async def endpoint_redbus(origen: str, destino: str, fecha: str, empresa: Optional[str] = None):
    """Busca buses en RedBus (todas las empresas o filtrado)."""
    resultado = await buscar_redbus(origen, destino, fecha, empresa)
    buses = sorted(resultado["resultados"], key=lambda x: x["hora_salida"])
    empresas = sorted(list(set(b["empresa"] for b in buses)))
    return {
        "exito": True,
        "fuente": "redbus",
        "origen": resultado["origen"],
        "destino": resultado["destino"],
        "fecha": fecha,
        "total_buses": len(buses),
        "empresas_disponibles": empresas,
        "horarios": buses,
    }

@app.get("/buscar-avanzado")
async def endpoint_avanzado(
    origen: str, destino: str, fecha: str,
    empresa: Optional[str] = None,
    precio_min: Optional[int] = None,
    precio_max: Optional[int] = None,
    hora_min: Optional[str] = None,
    hora_max: Optional[str] = None,
    asientos_min: Optional[int] = None,
    solo_ac: Optional[bool] = None,
    solo_cama: Optional[bool] = None,
    ordenar_por: Optional[str] = "hora",
):
    """Busca en RedBus con filtros avanzados."""
    resultado = await buscar_redbus(origen, destino, fecha, empresa)
    buses = resultado["resultados"]

    if precio_min: buses = [b for b in buses if b["precio_total"] >= precio_min]
    if precio_max: buses = [b for b in buses if b["precio_total"] <= precio_max]
    if hora_min:   buses = [b for b in buses if b["hora_salida"] >= hora_min]
    if hora_max:   buses = [b for b in buses if b["hora_salida"] <= hora_max]
    if asientos_min: buses = [b for b in buses if b["asientos_disponibles"] >= asientos_min]
    if solo_ac:    buses = [b for b in buses if b["es_ac"]]
    if solo_cama:  buses = [b for b in buses if b["es_cama"]]

    if ordenar_por == "precio":     buses.sort(key=lambda x: x["precio_total"])
    elif ordenar_por == "duracion": buses.sort(key=lambda x: x["duracion_minutos"])
    else:                           buses.sort(key=lambda x: x["hora_salida"])

    return {
        "exito": True,
        "fuente": "redbus",
        "origen": resultado["origen"],
        "destino": resultado["destino"],
        "fecha": fecha,
        "total_buses": len(buses),
        "horarios": buses,
    }

@app.get("/sillas/ochoa/{trip_id}")
async def sillas_ochoa(trip_id: str):
    """Sillas de un bus de Rápido Ochoa por trip_id."""
    sillas = await obtener_sillas_ochoa(trip_id)
    return {"exito": True, "fuente": "rapido_ochoa", "trip_id": trip_id, "sillas": sillas}

@app.get("/sillas/redbus")
async def sillas_redbus(
    origen: str, destino: str, fecha: str, hora_salida: str,
    empresa: Optional[str] = None,
):
    """Sillas de un bus en RedBus buscando por hora de salida."""
    resultado = await buscar_redbus(origen, destino, fecha, empresa)
    hora_norm = hora_salida if len(hora_salida.split(":")) == 3 else hora_salida + ":00"
    bus = next((b for b in resultado["resultados"] if b["hora_salida"] == hora_norm), None)
    if not bus:
        raise HTTPException(404, f"Bus no encontrado a las {hora_salida}")

    ciudad_o = buscar_ciudad(origen)
    ciudad_d = buscar_ciudad(destino)
    sillas = await obtener_sillas_redbus(
        route_id=bus["route_id"],
        operator_id=bus["operator_id"],
        fecha=fecha,
        from_city_name=ciudad_o["redbus_name"].replace(" (Todos)", ""),
        to_city_name=ciudad_d["redbus_name"].replace(" (Todos)", ""),
    )
    return {
        "exito": True,
        "fuente": "redbus",
        "bus": {"empresa": bus["empresa"], "hora_salida": hora_norm, "precio": bus["precio_total"]},
        "sillas": sillas,
    }

@app.post("/monitorear")
async def crear_monitor(
    origen: str, destino: str, fecha: str,
    fuente: str = "rapido_ochoa",
    horario: Optional[str] = None,
    empresa: Optional[str] = None,
):
    monitor = MonitorRuta(origen, destino, fecha, horario, empresa, fuente)
    rutas_monitoreadas[monitor.id] = monitor
    return {"exito": True, "mensaje": "Monitoreo iniciado", "monitor_id": monitor.id}

@app.get("/monitores")
async def listar_monitores():
    return {"total": len(rutas_monitoreadas), "monitores": [
        {"id": m.id, "origen": m.origen, "destino": m.destino, "fecha": m.fecha,
         "fuente": m.fuente, "activo": m.activo,
         "ultima_revision": m.ultima_revision.isoformat() if m.ultima_revision else None}
        for m in rutas_monitoreadas.values()
    ]}

@app.delete("/monitorear/{monitor_id}")
async def detener_monitor(monitor_id: str):
    if monitor_id not in rutas_monitoreadas:
        raise HTTPException(404, "Monitor no encontrado")
    rutas_monitoreadas[monitor_id].activo = False
    del rutas_monitoreadas[monitor_id]
    return {"exito": True, "mensaje": f"Monitor {monitor_id} detenido"}

@app.get("/alertas")
async def obtener_alertas(limite: int = 50):
    return {"total": len(alertas_generadas), "alertas": alertas_generadas[-limite:]}

@app.delete("/alertas")
async def limpiar_alertas():
    alertas_generadas.clear()
    return {"exito": True, "mensaje": "Alertas limpiadas"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
