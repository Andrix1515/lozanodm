# Control NiryoOne por mano (CoppeliaSim)

Programa mínimo: detecta tu mano con la cámara, muestra una **cuadrícula 3×3** y mueve el brazo en CoppeliaSim como un joystick. **Puño cerrado** → cierra la pinza.

## Requisitos

1. CoppeliaSim abierto con escena **NiryoOne** (no hace falta pulsar Play: `main.py` llama a `startSimulation()` igual que `simulacion_completa.py`).
2. Comprueba la conexión con `python simulacion_completa.py` si algo falla.
3. Cámara web conectada.
4. Python 3.10+

```powershell
pip install -r requirements.txt
python main.py
```

## Controles

| Acción | Efecto |
|--------|--------|
| Mano en celda lateral | Gira base (joint 1) |
| Mano arriba / abajo | Hombro (joint 2) |
| Esquinas | Combina ambos movimientos |
| Centro | Sin movimiento |
| Puño (≤1 dedo) | Cierra gripper |
| Mano abierta | Abre gripper + joystick |
| `H` | Posición HOME (todos los joints a 0) |
| `Q` | Salir |

## Estructura

```
main.py              # Punto de entrada
config.py            # Rutas joints, cámara, pasos del joystick
robot/coppelia.py    # Conexión ZMQ + gripper dinámico
vision/hand_control.py  # MediaPipe + cuadrícula 3×3
```

Las rutas de articulaciones coinciden con `simulacion_completa.py` (`/NiryoOne/...`).
