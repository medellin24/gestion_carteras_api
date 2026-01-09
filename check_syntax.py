import sys
import os

sys.path.append(os.getcwd())

try:
    import frames.frame_liquidacion
    print("Sintaxis correcta")
except IndentationError as e:
    print(f"Error de indentación: {e}")
except SyntaxError as e:
    print(f"Error de sintaxis: {e}")
except Exception as e:
    print(f"Otro error (ignorar): {e}")

