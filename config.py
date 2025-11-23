"""
Configuración del sistema de alertas
"""

CONFIG_ALERTAS = {
    "umbral_critico": 5,       # Alerta crítica cuando quedan menos de X asientos
    "umbral_advertencia": 10,   # Advertencia cuando quedan menos de X asientos
    "intervalo_revision": 300   # Revisar cada X segundos (300 = 5 minutos)
}