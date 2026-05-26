/**
 * Bus de eventos para extensiones futuras:
 * - WebSocket en tiempo real
 * - Grabación de secuencias
 * - Sincronización con brazo físico / visión por IA
 */

export const SimulatorEvents = {
  JOINTS_CHANGED: "joints-changed",
  TELEMETRY: "telemetry-changed",
  CONNECTION: "connection-changed",
  SEQUENCE_RECORD: "sequence-record",
  WS_MESSAGE: "ws-message",
};

/** Punto de conexión WebSocket (no implementado) */
export function connectRealtimeBridge(_url) {
  console.info("[events] WebSocket bridge: pendiente de implementación.");
  return null;
}
