# Control NiryoOne por mano (CoppeliaSim)

Programa mínimo: detecta tu mano con la cámara, muestra una **cuadrícula 3×3** y mueve el brazo en CoppeliaSim como un joystick. **Puño cerrado** → cierra la pinza.

## Requisitos

1. Python 3.10 o superior.
2. CoppeliaSim abierto con la escena **NiryoOne** cargada.
3. Cámara web conectada.
4. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

## Cómo probar el programa

1. Abre CoppeliaSim.
2. Carga la escena del robot NiryoOne.
3. Ejecuta el programa principal:

```powershell
python main.py
```

4. Si el programa lanza un error de MediaPipe relacionado con `mp.solutions`, instala la versión compatible:

```powershell
pip install mediapipe==0.10.5
```

5. Si la conexión con CoppeliaSim falla, prueba primero con:

```powershell
python simulacion_completa.py
```

5. Cuando se abra la ventana de la cámara, coloca tu mano sobre la cuadrícula.

## Controles

| Acción | Efecto |
|--------|--------|
| Mano en celda lateral | Gira base (joint 1) |
| Mano arriba / abajo | Mueve hombro (joint 2) |
| Esquinas | Combina ambos movimientos |
| Centro | Sin movimiento |
| Puño cerrado (≤1 dedo) | Cierra gripper |
| Mano abierta | Activa joystick de movimiento |
| `H` | Posición HOME (todos los joints a 0) |
| `C` | Calibrar |
| `Q` | Salir |

## Comprobaciones rápidas

- Si no se abre la cámara, revisa que la cámara web esté libre y funcionando.
- Si no se conecta a CoppeliaSim, comprueba que la escena NiryoOne esté cargada y que CoppeliaSim esté ejecutándose.
- Si el brazo no responde, revisa la consola para mensajes de error.

## Estructura principal

```
main.py                  # Punto de entrada
config.py                # Rutas joints, cámara, pasos del joystick
robot/coppelia.py        # Conexión ZMQ + gripper dinámico
vision/hand_control.py   # MediaPipe + cuadrícula 3×3
```

Las rutas de articulaciones coinciden con `simulacion_completa.py` (`/NiryoOne/...`).
