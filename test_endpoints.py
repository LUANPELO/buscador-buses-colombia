"""
Script para probar todos los endpoints de la API
Ejecutar después de iniciar el servidor: python test_endpoints.py
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def print_response(title, response):
    """Imprime respuesta formateada"""
    print(f"\n{'='*60}")
    print(f"🔹 {title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except:
        print(response.text)


def test_root():
    """Test endpoint raíz"""
    response = requests.get(f"{BASE_URL}/")
    print_response("TEST: Endpoint Raíz", response)


def test_buscar_ciudad():
    """Test buscar ciudad"""
    response = requests.get(f"{BASE_URL}/buscar-ciudad", params={"ciudad": "bogota"})
    print_response("TEST: Buscar Ciudad (Bogotá)", response)


def test_buscar_horarios():
    """Test buscar horarios"""
    # Fecha de mañana
    fecha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    params = {
        "origen": "barranquilla",
        "destino": "medellin",
        "fecha": fecha
    }
    
    response = requests.get(f"{BASE_URL}/buscar", params=params)
    print_response(f"TEST: Buscar Horarios (Barranquilla → Medellín, {fecha})", response)
    
    # Guardar para siguiente test
    if response.status_code == 200:
        data = response.json()
        if data.get("horarios") and len(data["horarios"]) > 0:
            return data["horarios"][0], fecha
    return None, fecha


def test_monitorear(horario_data, fecha):
    """Test monitorear ruta"""
    if not horario_data:
        print("\n⚠️  No hay horarios disponibles para monitorear")
        return None
    
    params = {
        "origen": "barranquilla",
        "destino": "medellin",
        "fecha": fecha,
        "horario": horario_data["hora_salida"][:5],  # Solo HH:MM
        "empresa": horario_data["empresa"].split()[0].lower()  # Primera palabra
    }
    
    response = requests.post(f"{BASE_URL}/monitorear", params=params)
    print_response(f"TEST: Monitorear Ruta ({params['horario']} - {params['empresa']})", response)
    
    if response.status_code == 200:
        return response.json().get("monitor", {}).get("id")
    return None


def test_ver_monitoreando():
    """Test ver rutas monitoreadas"""
    response = requests.get(f"{BASE_URL}/monitoreando")
    print_response("TEST: Ver Rutas Monitoreadas", response)


def test_alertas():
    """Test obtener alertas"""
    response = requests.get(f"{BASE_URL}/alertas")
    print_response("TEST: Obtener Todas las Alertas", response)
    
    # Filtrar por nivel
    response = requests.get(f"{BASE_URL}/alertas", params={"nivel": "CRITICO", "ultimas": 5})
    print_response("TEST: Alertas CRÍTICAS (últimas 5)", response)


def test_estado(monitor_id):
    """Test ver estado de ruta"""
    if not monitor_id:
        print("\n⚠️  No hay rutas para ver estado")
        return
    
    response = requests.get(f"{BASE_URL}/estado/{monitor_id}")
    print_response(f"TEST: Ver Estado de Ruta ({monitor_id})", response)


def test_configurar_alertas():
    """Test configurar umbrales"""
    params = {
        "umbral_critico": 3,
        "umbral_advertencia": 8,
        "intervalo_revision": 180
    }
    
    response = requests.put(f"{BASE_URL}/configurar-alertas", params=params)
    print_response("TEST: Configurar Umbrales de Alertas", response)


def main():
    """Ejecuta todos los tests"""
    print("🚀 INICIANDO PRUEBAS DE LA API")
    print(f"Base URL: {BASE_URL}")
    print("\n⚠️  IMPORTANTE: Asegúrate de que el servidor esté corriendo en {BASE_URL}")
    input("Presiona Enter para continuar...")
    
    try:
        # Test 1: Root
        test_root()
        
        # Test 2: Buscar ciudad
        test_buscar_ciudad()
        
        # Test 3: Buscar horarios
        horario_data, fecha = test_buscar_horarios()
        
        # Test 4: Monitorear ruta
        monitor_id = test_monitorear(horario_data, fecha)
        
        # Test 5: Ver rutas monitoreadas
        test_ver_monitoreando()
        
        # Test 6: Ver alertas
        test_alertas()
        
        # Test 7: Ver estado de ruta
        test_estado(monitor_id)
        
        # Test 8: Configurar alertas
        test_configurar_alertas()
        
        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: No se pudo conectar al servidor")
        print(f"Asegúrate de que el servidor esté corriendo en {BASE_URL}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")


if __name__ == "__main__":
    main()