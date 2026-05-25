# 🤖 Modular AI Robotic Arm Framework

**Control intuitivo de un brazo robótico mediante gestos de mano, API REST y controles por teclado.**

Construido con **CoppeliaSim**, **MediaPipe**, **OpenCV** y **Flask**.

---

## 🚀 Inicio Rápido

### 1. Instalar dependencias

```powershell
cd c:\Users\Asus\Desktop\robto\tecnologias\arm_robotic
pip install -r requirements.txt
```

### 2. Iniciar el programa

```powershell
python main.py
```

O simplemente:

```powershell
python starttt.py
```

### 3. Verás una ventana con:
- 📹 Captura en vivo de tu cámara
- 🎛️ Panel izquierdo con telemetría del sistema
- 👋 Reconocimiento de gestos en tiempo real
- 🤖 Estado del robot

---

## 📖 Documentación Completa

Para una **guía detallada con ejemplos**, consulta:

👉 **[GUIA_USUARIO.md](GUIA_USUARIO.md)** - Guía completa en español

Ahí encontrarás:
- ✅ Cómo hacer cada gesto
- ✅ Controles de teclado
- ✅ Modos de operación
- ✅ Ejemplos prácticos
- ✅ Troubleshooting
- ✅ API REST endpoints

---

## 🎮 Controles Principales

| Tecla | Acción |
|-------|--------|
| **C** | 📍 Calibrar mano |
| **M** | 🔄 Cambiar modo (GESTURE ↔ API_MANUAL) |
| **A** | 🤖 Prueba automática (pick-and-place) |
| **H** | 🏠 Mover a HOME |
| **S** | 🛑 Stop / Abrir garra |
| **Q** | ❌ Salir |

---

## 👋 Gestos Reconocidos

1. **MANO ABIERTA** ✋ → Detiene y abre garra
2. **MANO CERRADA** ✊ → Cierra garra
3. **MANO A LA IZQUIERDA** 👈 → Zona LEFT
4. **MANO A LA DERECHA** 👉 → Zona RIGHT
5. **PULGAR ARRIBA** 👍 → HOME

---

## 🌐 API REST

El servidor REST escucha en `http://127.0.0.1:5000`

### Ejemplos de uso:

```bash
# Obtener estado
curl http://127.0.0.1:5000/api/state

# Mover a LEFT
curl -X POST http://127.0.0.1:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "move_to_zone", "zone": "LEFT"}'

# Cerrar garra
curl -X POST http://127.0.0.1:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"action": "close_gripper"}'
```

Ver **[GUIA_USUARIO.md](GUIA_USUARIO.md)** para todos los endpoints.

---

## ⚡ Optimizaciones Implementadas

✅ **Frame skipping** - Procesa cada 2 frames (reducción CPU)  
✅ **Resolución optimizada** - 480x360 (en lugar de 640x480)  
✅ **MediaPipe ajustado** - Mayor confianza, menos falsos positivos  
✅ **Monitor de FPS** - Visible en el panel izquierdo  
✅ **Suavizado adaptativo** - Movimientos fluidos con baja latencia

---

## 📁 Estructura del Proyecto

```
arm_robotic/
├── main.py                  # Punto de entrada principal
├── starttt.py              # Proxy alternativo
├── config.py               # Configuración global
├── GUIA_USUARIO.md         # Guía completa (🌟 LEER ESTO)
├── requirements.txt        # Dependencias Python
├── README.md              # Este archivo
│
├── ai/                     # Sistema de visión y gestos
│   ├── vision.py          # Procesamiento de cámara y HUD
│   ├── gestures.py        # Clasificador de gestos
│   └── __init__.py
│
├── robot/                 # Adaptadores de robot
│   ├── base_robot.py      # Interfaz abstracta
│   ├── coppelia_robot.py  # Simulador CoppeliaSim
│   ├── arduino_robot.py   # Hardware Arduino (mock)
│   └── __init__.py
│
├── api/                   # Servidor REST
│   ├── server.py          # Flask server y endpoints
│   └── __init__.py
│
├── control/               # Lógica de automatización
│   ├── actions.py         # Rutinas pick-and-place
│   ├── positions.py       # Definición de posiciones (si existe)
│   └── __init__.py
│
└── utils/                 # Utilidades
    └── __init__.py
```

---

## ⚙️ Configuración

Edita `config.py` para:

- Cambiar adaptador: `ROBOT_ADAPTER = "coppelia"` o `"arduino"`
- Ajustar resolución de cámara
- Cambiar puertos de conexión
- Definir nuevas zonas de trabajo

---

## 🔧 Requisitos del Sistema

- **Python** 3.10+
- **CoppeliaSim** (si usas simulación)
- **Cámara web** conectada
- **Windows/Linux/Mac**

---

## 📚 Recursos

- [Guía completa de usuario](GUIA_USUARIO.md)
- [Documentación MediaPipe](https://developers.google.com/mediapipe)
- [CoppeliaSim Documentation](https://www.coppeliarobotics.com/helpFiles/)

---

## 🐛 ¿Problemas?

1. Consulta la **[Guía de Usuario](GUIA_USUARIO.md)** - Sección "Troubleshooting"
2. Verifica que `config.py` esté bien configurado
3. Asegúrate que CoppeliaSim esté con simulación en play
4. Revisa los mensajes en la consola

---

## 📝 Licencia

Este proyecto es de código abierto. Siéntete libre de modificarlo y adaptarlo.

---

## 🎯 Funcionalidades Clave

- ✅ Reconocimiento de gestos en tiempo real
- ✅ Control por API REST
- ✅ Múltiples modos operacionales
- ✅ Rutinas pick-and-place automáticas
- ✅ Panel de telemetría en vivo
- ✅ Suavizado de movimientos
- ✅ Seguridad (e-stop)
- ✅ Arquitectura modular

---

## 🚀 Próximas Mejoras

- [ ] Grabación de macros personalizadas
- [ ] Interface web de control
- [ ] Soporte para múltiples robots
- [ ] Machine learning para gestos personalizados
- [ ] Integración con ROS

---

**¡Listo para controlar tu robot!** 🤖✨

**Comienza aquí:** 👉 [Guía de Usuario Completa](GUIA_USUARIO.md)
