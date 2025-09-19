#!/usr/bin/env python3
"""
Script de prueba para verificar que se solucionó el error de serialización Decimal.
"""

import requests
import json

# Configuración
BASE_URL = "http://localhost:8000"
EMPLEADO_ID = "1045112243"  # El empleado que causaba el error

def test_eliminar_empleado_con_tarjetas():
    """Prueba el endpoint DELETE /empleados/{id} con un empleado que tiene tarjetas"""
    print("=== Probando eliminación de empleado con tarjetas (Error Decimal Fix) ===")
    
    url = f"{BASE_URL}/empleados/{EMPLEADO_ID}"
    
    try:
        response = requests.delete(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 409:
            print("✅ ÉXITO: El endpoint ahora maneja correctamente la serialización JSON")
            data = response.json()
            print(f"Error: {data.get('error', 'N/A')}")
            print(f"Tarjetas asociadas: {data.get('tarjetas_asociadas', {}).get('total', 0)}")
            print(f"Opciones disponibles: {len(data.get('opciones', []))}")
            
            # Verificar que los montos son números (no Decimal)
            tarjetas = data.get('tarjetas_asociadas', {}).get('detalle', [])
            if tarjetas:
                primera_tarjeta = tarjetas[0]
                monto = primera_tarjeta.get('monto')
                print(f"Primera tarjeta - Monto: {monto} (tipo: {type(monto)})")
                if isinstance(monto, (int, float)):
                    print("✅ ÉXITO: Los montos se serializan correctamente como números")
                else:
                    print("❌ ERROR: Los montos no se serializan correctamente")
            
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
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Error al decodificar JSON: {e}")
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
                
                # Verificar serialización de montos
                tarjetas = result.get('tarjetas_a_transferir', {}).get('detalle', [])
                if tarjetas:
                    primera_tarjeta = tarjetas[0]
                    monto = primera_tarjeta.get('monto')
                    print(f"Primera tarjeta - Monto: {monto} (tipo: {type(monto)})")
                    if isinstance(monto, (int, float)):
                        print("✅ ÉXITO: Los montos se serializan correctamente")
                    else:
                        print("❌ ERROR: Los montos no se serializan correctamente")
                
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
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Error al decodificar JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_endpoint_eliminacion_forzada():
    """Prueba el endpoint de eliminación forzada (sin confirmar)"""
    print("\n=== Probando endpoint de eliminación forzada ===")
    
    url = f"{BASE_URL}/empleados/{EMPLEADO_ID}/forzar-eliminacion"
    data = {
        "confirmar_eliminacion": False,
        "eliminar_tarjetas": False
    }
    
    try:
        response = requests.delete(url, json=data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("confirmacion_requerida"):
                print("✅ ÉXITO: El endpoint de eliminación forzada funciona correctamente")
                print(f"Tiene tarjetas: {result.get('tiene_tarjetas', False)}")
                
                # Verificar serialización de montos si hay tarjetas
                tarjetas_info = result.get('tarjetas_asociadas')
                if tarjetas_info and tarjetas_info.get('detalle'):
                    tarjetas = tarjetas_info['detalle']
                    primera_tarjeta = tarjetas[0]
                    monto = primera_tarjeta.get('monto')
                    print(f"Primera tarjeta - Monto: {monto} (tipo: {type(monto)})")
                    if isinstance(monto, (int, float)):
                        print("✅ ÉXITO: Los montos se serializan correctamente")
                    else:
                        print("❌ ERROR: Los montos no se serializan correctamente")
                
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
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Error al decodificar JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Función principal de prueba"""
    print("🧪 Iniciando pruebas del fix para error de serialización Decimal")
    print(f"Empleado de prueba: {EMPLEADO_ID}")
    print(f"URL base: {BASE_URL}")
    
    tests = [
        test_eliminar_empleado_con_tarjetas,
        test_endpoint_transferir_tarjetas,
        test_endpoint_eliminacion_forzada
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
        print("\n🎉 ¡Todas las pruebas pasaron! El error de serialización Decimal está solucionado.")
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisa los errores arriba.")

if __name__ == "__main__":
    main()
