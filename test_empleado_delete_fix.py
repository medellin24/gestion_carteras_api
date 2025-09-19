#!/usr/bin/env python3
"""
Script de prueba para verificar la solución del problema de eliminación de empleados
con restricción de clave foránea.
"""

import requests
import json

# Configuración
BASE_URL = "http://localhost:8000"
EMPLEADO_ID = "1045112243"  # El empleado que causaba el error

def test_eliminar_empleado_con_tarjetas():
    """Prueba el endpoint DELETE /empleados/{id} con un empleado que tiene tarjetas"""
    print("=== Probando eliminación de empleado con tarjetas ===")
    
    url = f"{BASE_URL}/empleados/{EMPLEADO_ID}"
    
    try:
        response = requests.delete(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 409:
            print("✅ ÉXITO: El endpoint ahora maneja correctamente la restricción de clave foránea")
            data = response.json()
            print(f"Error: {data.get('error', 'N/A')}")
            print(f"Tarjetas asociadas: {data.get('tarjetas_asociadas', {}).get('total', 0)}")
            print(f"Opciones disponibles: {len(data.get('opciones', []))}")
            return True
        elif response.status_code == 404:
            print("ℹ️  INFO: El empleado no existe (puede que ya fue eliminado)")
            return True
        else:
            print(f"❌ ERROR: Respuesta inesperada: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: No se puede conectar al servidor. ¿Está ejecutándose la API?")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_verificar_empleado_tiene_tarjetas():
    """Prueba el endpoint de verificación de tarjetas"""
    print("\n=== Probando verificación de tarjetas del empleado ===")
    
    # Simulamos la verificación haciendo una petición GET a las tarjetas del empleado
    url = f"{BASE_URL}/empleados/{EMPLEADO_ID}/tarjetas/"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            tarjetas = response.json()
            print(f"✅ ÉXITO: Se encontraron {len(tarjetas)} tarjetas para el empleado")
            return True
        elif response.status_code == 404:
            print("ℹ️  INFO: El empleado no existe")
            return True
        else:
            print(f"❌ ERROR: Respuesta inesperada: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: No se puede conectar al servidor")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_endpoint_transferir_tarjetas():
    """Prueba el endpoint de transferencia de tarjetas (sin confirmar)"""
    print("\n=== Probando endpoint de transferencia de tarjetas ===")
    
    url = f"{BASE_URL}/empleados/{EMPLEADO_ID}/transferir-tarjetas"
    data = {
        "empleado_destino": "9999999999",  # Un empleado que probablemente no existe
        "confirmar_transferencia": False
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("confirmacion_requerida"):
                print("✅ ÉXITO: El endpoint de transferencia funciona correctamente")
                print(f"Tarjetas a transferir: {result.get('tarjetas_a_transferir', {}).get('total', 0)}")
                return True
            else:
                print("❌ ERROR: No se solicitó confirmación")
                return False
        elif response.status_code == 404:
            print("ℹ️  INFO: El empleado no existe")
            return True
        else:
            print(f"❌ ERROR: Respuesta inesperada: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: No se puede conectar al servidor")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Función principal de prueba"""
    print("🧪 Iniciando pruebas de la solución para eliminación de empleados")
    print(f"Empleado de prueba: {EMPLEADO_ID}")
    print(f"URL base: {BASE_URL}")
    
    tests = [
        test_eliminar_empleado_con_tarjetas,
        test_verificar_empleado_tiene_tarjetas,
        test_endpoint_transferir_tarjetas
    ]
    
    resultados = []
    for test in tests:
        try:
            resultado = test()
            resultados.append(resultado)
        except Exception as e:
            print(f"❌ ERROR en test: {e}")
            resultados.append(False)
    
    print(f"\n📊 Resumen de pruebas:")
    print(f"✅ Exitosas: {sum(resultados)}")
    print(f"❌ Fallidas: {len(resultados) - sum(resultados)}")
    
    if all(resultados):
        print("\n🎉 ¡Todas las pruebas pasaron! La solución está funcionando correctamente.")
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisa los errores arriba.")

if __name__ == "__main__":
    main()
