# 📖 GUÍA COMPLETA - Sistema de Control Robótico por Gestos

## 🎯 Visión General

Este es un **Sistema Modular de Control de Brazo Robótico** que permite controlar un robot (simulado en CoppeliaSim o físico con Arduino) mediante:

1. **Gestos de la mano** - Reconocimiento por MediaPipe
2. **API REST** - Comandos HTTP desde aplicaciones externas
3. **Modos manuales** - Control por teclado

---

## 🚀 Inicio Rápido

### 1. Instalación de dependencias

```powershell
pip install opencv-python mediapipe numpy flask coppeliasim-zmqremoteapi-client
```

### 2. Arrancar el programa

```powershell
cd c:\Users\Asus\Desktop\robto\tecnologias\arm_robotic
python main.py
```

O alternativamente:

```powershell
python starttt.py
```

### 3. Esperar a que inicie

Verás esto en la consola:

```
==================================================================
      MODULAR AI ROBOTIC ARM FRAMEWORK - INITIALIZATION           
==================================================================
[System] Target Adapter Type  : COPPELIAROBOTADAPTER
[System] REST Server Endpoint : http://127.0.0.1:5000
==================================================================

[CoppeliaAdapter] Successfully connected and initialized joints.
[Vision] Opening camera with index 0...

[System] HUD Window opened. Focus on the CV2 window to use keyboard hotkeys.
```

Una ventana con la cámara se abrirá mostrando:
- Tu mano capturada por la cámara
- Panel izquierdo con telemetría del sistema
- Estado de conexión del robot
- FPS actual

---

## 👋 Gestos de Mano - Modo GESTURE

El programa reconoce **5 gestos discretos** de tu mano:

### 1. **MANO ABIERTA (OPEN)** ✋
- **Descripción**: Todos los dedos extendidos
- **Efecto**: Detiene el robot y abre la garra
- **Cómo hacerlo**: Abre la mano completamente, dedos separados

### 2. **MANO CERRADA (CLOSED)** ✊
- **Descripción**: Puño completamente cerrado
- **Efecto**: Cierra la garra del robot
- **Cómo hacerlo**: Cierra los dedos en puño

### 3. **MANO INCLINADA A LA IZQUIERDA (TILT_LEFT)** 👈
- **Descripción**: Mano desplazada a la izquierda de tu cuerpo
- **Efecto**: Mueve el robot a la **ZONA IZQUIERDA (LEFT)**
- **Cómo hacerlo**: Levanta la mano y muévela lentamente hacia la izquierda

### 4. **MANO INCLINADA A LA DERECHA (TILT_RIGHT)** 👉
- **Descripción**: Mano desplazada a la derecha de tu cuerpo
- **Efecto**: Mueve el robot a la **ZONA DERECHA (RIGHT)**
- **Cómo hacerlo**: Levanta la mano y muévela lentamente hacia la derecha

### 5. **PULGAR HACIA ARRIBA (THUMB_UP)** 👍
- **Descripción**: Pulgar extendido hacia arriba, otros dedos cerrados
- **Efecto**: Mueve el robot a la **POSICIÓN HOME** (posición de reposo)
- **Cómo hacerlo**: Cierra el puño y extiende solo el pulgar hacia arriba

---

## ⌨️ Controles de Teclado

Presiona estas teclas con la **ventana de la cámara enfocada**:

| Tecla | Acción | Descripción |
|-------|--------|-------------|
| **C** | Calibrar | Calibra el centro neutral de tu mano. Posiciona la mano en pose natural |
| **M** | Cambiar Modo | Alterna entre **GESTURE** ↔ **API_MANUAL** |
| **A** | Prueba Automática | Ejecuta una prueba de pick-and-place: coge de LEFT, suelta en DROP_ZONE |
| **H** | Home | Mueve el brazo a la posición de reposo (HOME) |
| **S** | Stop & Abrir Garra | Detiene todos los movimientos e inmediatamente abre la garra |
| **Q** | Salir | Cierra el programa de forma segura |

---

## 🎮 Modos de Operación

El programa tiene **3 modos principales**:

### 1. **GESTURE** (Modo Gestos) 🤖
- **Estado**: Activo por defecto
- **Control**: Mediante gestos de mano
- **Ideal para**: Control intuitivo en tiempo real
- **Cambiar a**: Presiona **M**

### 2. **API_MANUAL** (Modo API Manual) 🌐
- **Estado**: Control por HTTP REST
- **Control**: Mediante peticiones HTTP desde aplicaciones externas
- **Ideal para**: Integración con otras aplicaciones, automatización
- **Cambiar a**: Presiona **M**

En este modo NO puedes usar gestos - debes enviar comandos HTTP:

```bash
# Ejemplo: Mover a zona LEFT
curl -X POST http://127.0.0.1:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "move_to_zone", "zone": "LEFT"}'

# Cerrar garra
curl -X POST http://127.0.0.1:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "close_gripper"}'

# Abrir garra
curl -X POST http://127.0.0.1:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "open_gripper"}'
```

### 3. **AUTONOMOUS** (Modo Autónomo)
- **Estado**: Se activa cuando ejecutas "Prueba Automática" (**A**)
- **Control**: Rutina pre-programada pick-and-place
- **Secuencia**:
  1. Mueve a zona SOURCE
  2. Abre garra
  3. Baja y recoge objeto
  4. Sube y traslada a zona TARGET
  5. Baja y suelta objeto
  6. Regresa a HOME

---

## 🎯 Flujo de Trabajo Típico

### Escenario 1: Coger un objeto de la izquierda y dejarlo en la zona de descarga

1. **Asegúrate que el modo es GESTURE** (presiona **M** hasta verlo en pantalla)
2. **Calibra tu mano**: 
   - Posiciona la mano en pose natural frente a la cámara
   - Presiona **C**
   - Verás "Calibration acquired!" en el panel izquierdo

3. **Abre la mano** (gesto OPEN):
   - El robot abrirá la garra y se detendrá
   - Estado en pantalla: "Sending discrete: stop"

4. **Inclina la mano a la izquierda** (gesto TILT_LEFT):
   - El robot se moverá a la zona LEFT
   - Espera a que termine (observable en el panel izquierdo)

5. **Cierra la mano** (gesto CLOSED):
   - El robot cierra la garra para agarrar el objeto
   - Espera 2 segundos

6. **Inclina la mano a la derecha o usa tecla A**:
   - Mueve hacia la derecha (RIGHT) o
   - Presiona **A** para que haga automático pick-and-place

7. **Abre la mano** (gesto OPEN):
   - El robot abre la garra y suelta el objeto

8. **Pulgar hacia arriba** (gesto THUMB_UP):
   - El robot regresa a HOME (posición de reposo)

---

## 🔧 Configuración

Archivo: `config.py`

### Parámetros principales:

```python
# Qué robot usar
ROBOT_ADAPTER = "coppelia"  # o "arduino" para modo simulado

# Cámara
FRAME_WIDTH = 480      # Ancho en píxeles (reducido para más velocidad)
FRAME_HEIGHT = 360     # Alto en píxeles (reducido para más velocidad)
TARGET_FPS = 30        # Fotogramas por segundo objetivo

# Suavizado de movimientos
SMOOTHING_ALPHA = 0.35  # 0=muy suave, 1=sin suavizado

# API REST
API_HOST = "127.0.0.1"
API_PORT = 5000

# Zonas predefinidas (posiciones del robot)
PRESET_POSITIONS_6DOF = {
    "HOME": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "LEFT": [30°, -45°, 20°, -10°, 45°, 10°],
    "CENTER": [0°, -40°, 25°, -15°, 30°, 5°],
    "RIGHT": [-30°, -45°, 20°, 10°, 45°, -10°],
    "DROP_ZONE": [60°, -35°, 35°, -5°, 50°, -20°]
}
```

---

## 🌐 API REST - Endpoints

Base URL: `http://127.0.0.1:5000`

### 1. Obtener estado del sistema

```bash
GET /api/state
```

**Respuesta:**
```json
{
  "status": "success",
  "robot": {
    "adapter": "Coppelia",
    "connected": true,
    "joint_positions": [0.0, -0.5, 0.3, -0.2, 0.8, 0.1],
    "gripper_closed": false,
    "current_pose": "HOME"
  },
  "vision": {
    "hand_detected": true,
    "current_mode": "GESTURE",
    "current_gesture": "OPEN"
  }
}
```

### 2. Cambiar modo de operación

```bash
POST /api/mode
Content-Type: application/json

{
  "mode": "API_MANUAL"  # o "GESTURE" o "AUTONOMOUS"
}
```

### 3. Enviar comando al robot

```bash
POST /api/command
Content-Type: application/json

{
  "action": "move_to_zone",
  "zone": "LEFT"
}
```

**Acciones disponibles:**
- `"move_home"` - Mover a HOME
- `"move_to_zone"` con `zone` (LEFT, CENTER, RIGHT, DROP_ZONE)
- `"open_gripper"` - Abrir garra
- `"close_gripper"` - Cerrar garra
- `"pick_place"` con `source` y `target` - Pick-and-place automático
- `"stop"` - Detener todo

---

## ⚙️ Optimizaciones Implementadas

El programa ha sido optimizado para mejorar velocidad:

✅ **Frame skipping** - Procesa MediaPipe cada 2 frames (menos carga CPU)
✅ **Resolución reducida** - De 640x480 a 480x360 (más rápido)
✅ **Mayor confianza en MediaPipe** - Menos falsos positivos, menos procesamiento
✅ **Suavizado adaptativo** - Movimientos más fluidos con menos latencia
✅ **Monitor de FPS** - Verás los FPS en tiempo real en el panel izquierdo

---

## 🐛 Troubleshooting

### Problema: "The term 'head' is not recognized"
**Solución**: Es un error de PowerShell. Ignóralo, el programa funciona bien.

### Problema: La cámara no se abre
**Solución**: 
- Verifica que tu cámara esté conectada
- Cambia `CAMERA_INDEX` en `config.py` (prueba 0, 1, 2...)
- Asegúrate de que ninguna otra aplicación use la cámara

### Problema: El robot no se mueve
**Solución**:
- Verifica que CoppeliaSim esté abierto y la simulación en play
- Comprueba que el adaptador sea el correcto: `config.ROBOT_ADAPTER = "coppelia"`
- En el panel izquierdo busca "Connection: CONNECTED"

### Problema: Los gestos no se reconocen
**Solución**:
- Primero **calibra** presionando **C** con la mano en pose natural
- Asegúrate de moverte lentamente
- Ten buena iluminación
- Abre la mano completamente (todos los dedos extendidos para OPEN)

### Problema: El programa es lento
**Soluciones ya aplicadas:**
- Frame skipping habilitado
- Resolución reducida a 480x360
- MediaPipe optimizado

Si sigue lento:
- Aumenta `frame_skip` en `vision.py` (valor 3 o 4)
- Reduce más la resolución en `config.py`

---

## 📊 Panel Izquierdo - Explicación del HUD

El panel izquierdo muestra:

```
┌──────────────────────────┐
│  MODULAR ROBOTIC ARM     │
│  AI FRAMEWORK V1.0       │
├──────────────────────────┤
│ SYSTEM STATUS            │
│ Hardware: Coppelia       │
│ Connection: CONNECTED    │
│ Mode: GESTURE            │
│ Hand Track: ACQUIRED     │
├──────────────────────────┤
│ AI RECOGNITION CARD      │
│ Discrete Gesture: OPEN   │
│ Active Command: STOP     │
├──────────────────────────┤
│ TELEMETRY LOGS           │
│ Status message aquí      │
└──────────────────────────┘
```

**Colores:**
- 🟢 Verde = Conectado / Correcto
- 🔴 Rojo = Desconectado / Error
- 🟡 Amarillo = Buscando / Neutral
- 🔵 Azul = Información

---

## 📝 Notas Importantes

1. **Calibración**: Siempre calibra al inicio presionando **C**
2. **Gestos lentos**: Mueve la mano lentamente para que se reconozca
3. **Modo GESTURE**: No puedes usar API mientras está activo. Cambia a API_MANUAL
4. **Seguridad**: Presiona **S** en emergencia para detener todo
5. **Salida segura**: Presiona **Q** para cerrar correctamente

---

## 🎓 Ejemplos Prácticos

### Ejemplo 1: Pick-and-Place manual paso a paso

```
1. Presiona C para calibrar
2. Abre mano (OPEN) → Robot abre garra
3. Inclina izquierda (TILT_LEFT) → Va a LEFT
4. Cierra mano (CLOSED) → Agarra objeto
5. Inclina derecha (TILT_RIGHT) → Va a RIGHT
6. Abre mano (OPEN) → Suelta objeto
7. Pulgar arriba (THUMB_UP) → Regresa a HOME
```

### Ejemplo 2: Usar API desde Python

```python
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

# 1. Cambiar a modo API_MANUAL
requests.post(f"{BASE_URL}/api/mode", json={"mode": "API_MANUAL"})

# 2. Mover a LEFT
requests.post(f"{BASE_URL}/api/command", json={"action": "move_to_zone", "zone": "LEFT"})

# 3. Cerrar garra
requests.post(f"{BASE_URL}/api/command", json={"action": "close_gripper"})

# 4. Mover a DROP_ZONE
requests.post(f"{BASE_URL}/api/command", json={"action": "move_to_zone", "zone": "DROP_ZONE"})

# 5. Abrir garra
requests.post(f"{BASE_URL}/api/command", json={"action": "open_gripper"})

# 6. Obtener estado
response = requests.get(f"{BASE_URL}/api/state")
print(json.dumps(response.json(), indent=2))
```

---

## 📞 Soporte

Si tienes problemas:

1. Verifica el archivo `config.py` esté correctamente configurado
2. Revisa la consola para mensajes de error
3. Asegúrate que CoppeliaSim esté con la simulación en play
4. Prueba en modo GESTURE primero antes de API_MANUAL

---

**¡Listo para controlar tu robot por gestos!** 🤖✨
