"""
Positions Registry — v2.0 (sin cambios funcionales, añadida zona CENTER)
─────────────────────────────────────────────────────────────────────────
Registra, traduce y valida coordenadas de control discretas para presets de zonas.
"""

import config


def get_zone_angles(zone_name: str, adapter_type: str) -> list:
    """
    Devuelve los ángulos articulares objetivo para una zona y adaptador dados.

    Args:
        zone_name:    'HOME' | 'LEFT' | 'CENTER' | 'RIGHT' | 'DROP_ZONE'
        adapter_type: 'coppelia' | 'arduino'

    Returns:
        Lista de valores articulares (radianes para coppelia, grados para arduino).
    """
    zone_upper = zone_name.upper()

    if adapter_type == "coppelia":
        presets = config.PRESET_POSITIONS_6DOF
        return presets.get(zone_upper, presets["HOME"])
    else:
        presets = config.PRESET_POSITIONS_4DOF
        return presets.get(zone_upper, presets["HOME"])


def get_available_zones(adapter_type: str) -> list:
    """Retorna la lista de zonas configuradas para el adaptador actual."""
    if adapter_type == "coppelia":
        return list(config.PRESET_POSITIONS_6DOF.keys())
    return list(config.PRESET_POSITIONS_4DOF.keys())