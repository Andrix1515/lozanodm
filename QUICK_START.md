# ⚡ QUICK START - 3 PASOS PARA EMPEZAR

## 1️⃣ Instalar Dependencias (Una sola vez)

Abre PowerShell en la carpeta del proyecto:

```powershell
pip install -r requirements.txt
```

**¿Ya instalado?** Salta al paso 2.

---

## 2️⃣ Iniciar el Programa

```powershell
python main.py
```

Espera a ver:
```
[System] HUD Window opened. Focus on the CV2 window to use keyboard hotkeys.
```

---

## 3️⃣ ¡Usar!

### Primero: **CALIBRA** (Solo al inicio)
Presiona **C** con la mano en posición natural frente a la cámara.

### Luego: Prueba los **5 gestos**

| Gesto | Cómo hacerlo | Qué pasa |
|-------|-------------|---------|
| 🖐️ **Mano abierta** | Dedos extendidos | Garra abierta, robot para |
| ✊ **Puño cerrado** | Todos dedos cerrados | Garra cierra |
| 👈 **Mano izquierda** | Mano a la izquierda | Brazo va a LEFT |
| 👉 **Mano derecha** | Mano a la derecha | Brazo va a RIGHT |
| 👍 **Pulgar arriba** | Solo pulgar extendido | Brazo vuelve a HOME |

---

## 🎮 Teclas de Control

| Tecla | Qué hace |
|-------|----------|
| **C** | 📍 Calibrar |
| **M** | 🔄 Cambiar modo |
| **A** | 🤖 Prueba automática |
| **H** | 🏠 Home |
| **S** | 🛑 Stop |
| **Q** | ❌ Salir |

---

## 📖 ¿Quieres Aprender Más?

Lee: **[GUIA_USUARIO.md](GUIA_USUARIO.md)** para:
- Explicación detallada de cada gesto
- Cómo usar la API REST
- Ejemplos prácticos
- Solución de problemas
- Configuración avanzada

---

## ⚡ Optimizaciones Aplicadas

El programa ya está **optimizado para velocidad**:

✅ Resolución reducida (480x360)  
✅ Frame skipping inteligente  
✅ MediaPipe configurado para velocidad  
✅ Latencia mínima  
✅ FPS mejorado

Ver: **[OPTIMIZACIONES.md](OPTIMIZACIONES.md)** para detalles técnicos.

---

## 🐛 ¿Algo no funciona?

**Problema**: La cámara no se abre
- Verifica que esté conectada
- Intenta cambiar `CAMERA_INDEX` en `config.py`

**Problema**: El robot no responde
- Asegúrate que CoppeliaSim esté con simulación en **PLAY**
- Verifica que dice "Connection: CONNECTED" en la pantalla

**Problema**: Los gestos no se reconocen
- Primero **calibra** presionando **C**
- Muévete lentamente
- Ten buena iluminación

**Más problemas**: Lee la sección "Troubleshooting" en **[GUIA_USUARIO.md](GUIA_USUARIO.md)**

---

## 🎉 ¡Listo!

Ahora tienes:
- ✅ Reconocimiento de gestos
- ✅ Control de robot simulado o real
- ✅ API REST para automatización
- ✅ Panel de telemetría en vivo
- ✅ Velocidad optimizada

**¡Diviértete controlando tu robot!** 🤖✨

---

## 📚 Archivos Importantes

| Archivo | Propósito |
|---------|-----------|
| `README.md` | Documentación principal |
| `GUIA_USUARIO.md` | Guía completa con ejemplos |
| `OPTIMIZACIONES.md` | Detalles técnicos de mejoras |
| `QUICK_START.md` | Este archivo |
| `config.py` | Configuración del sistema |
| `main.py` | Punto de entrada |
| `requirements.txt` | Dependencias |

---

**Próximo paso**: 👉 [Lee la Guía Completa](GUIA_USUARIO.md)
