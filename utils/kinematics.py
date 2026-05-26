import logging
import math
from collections import deque
from typing import Deque, Dict, Tuple

import config

logger = logging.getLogger(__name__)


class AdaptiveEMAFilter:
    """Filtro exponencial adaptativo para los valores de posición de la mano."""

    def __init__(
        self,
        alpha_min: float = 0.15,
        alpha_max: float = 0.7,
        tremor_std_threshold: float = 2.5,
        max_history: int = 5,
    ):
        self.alpha_min = alpha_min
        self.alpha_max = alpha_max
        self.tremor_std_threshold = tremor_std_threshold
        self._filtered_value: float | None = None
        self._history: Deque[float] = deque(maxlen=max_history)

    def reset(self):
        """Reinicia el estado del filtro a su estado inicial."""
        self._filtered_value = None
        self._history.clear()

    def update(self, value: float) -> float:
        """Actualiza el filtro con un nuevo valor y devuelve el valor filtrado."""
        if self._filtered_value is None:
            self._filtered_value = value
            self._history.append(value)
            return value

        delta = abs(value - self._filtered_value)
        self._history.append(value)
        if (
            len(self._history) == self._history.maxlen
            and self._standard_deviation(self._history) >= self.tremor_std_threshold
            and delta < 5.0
        ):
            return self._filtered_value

        alpha = self._select_alpha(delta)
        self._filtered_value += alpha * (value - self._filtered_value)
        return self._filtered_value

    @staticmethod
    def _standard_deviation(values: Deque[float]) -> float:
        mean_value = sum(values) / len(values)
        return math.sqrt(sum((x - mean_value) ** 2 for x in values) / len(values))

    def _select_alpha(self, delta: float) -> float:
        if delta < 5.0:
            return self.alpha_min
        if delta > 20.0:
            return self.alpha_max
        ratio = (delta - 5.0) / 15.0
        return self.alpha_min + ratio * (self.alpha_max - self.alpha_min)


def clamp_joint_angles(angles_dict: Dict[str, float]) -> Dict[str, float]:
    """Clamp joint angles using the physical limits defined in config.JOINT_LIMITS.

    Args:
        angles_dict: Mapping from joint names to target angles in degrees.

    Returns:
        A new dict where every known joint value is clamped to its configured range.
    """
    corrected: Dict[str, float] = {}

    for joint_name, angle in angles_dict.items():
        limits: Tuple[float, float] | None = config.JOINT_LIMITS.get(joint_name)
        if limits is None:
            corrected[joint_name] = angle
            continue

        lower_limit, upper_limit = limits
        clamped_angle = min(max(angle, lower_limit), upper_limit)
        if clamped_angle != angle:
            logger.warning(
                "Ángulo de %s recortado de %.2f° a %.2f° según JOINT_LIMITS.",
                joint_name,
                angle,
                clamped_angle,
            )
        corrected[joint_name] = clamped_angle

    return corrected


def is_near_singularity(angles_dict: Dict[str, float]) -> Tuple[bool, str]:
    """Detecta configuraciones cercanas a una singularidad del NiryoOne.

    El robot se considera cercano a singularidad si:
      - joint3 está cerca de 0°
      - joint5 está cerca de ±90°

    Args:
        angles_dict: Mapping of joint names to angles in degrees.

    Returns:
        Un par (is_singular, mensaje). Si el valor es True, el mensaje indica el motivo.
    """
    joint3 = angles_dict.get("joint3")
    joint5 = angles_dict.get("joint5")

    singularity_threshold_deg = 5.0

    if joint3 is not None and abs(joint3) <= singularity_threshold_deg:
        return True, "joint3 está demasiado cerca de 0°; posible configuración singular."

    if joint5 is not None and abs(abs(joint5) - 90.0) <= singularity_threshold_deg:
        return True, "joint5 está demasiado cerca de ±90°; posible configuración singular."

    return False, "No se detectó singularidad cercana."
