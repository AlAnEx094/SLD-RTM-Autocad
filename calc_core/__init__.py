"""
calc_core — расчётное ядро SLD-RTM-AutoCAD.

MVP-0.1:
- Kr-lookup по SQLite (контракт в docs/contracts/KR_RESOLVER.md)
- расчёт формы Ф636-92 для одного щита (контракт в docs/contracts/RTM_F636.md)

DWG/AutoCAD интеграция намеренно отсутствует: в архитектуре DWG = рендер.
"""

from .kr_resolver import get_kr, resolve_kr
from .rtm_f636 import run_panel_calc

__all__ = [
    "get_kr",
    "resolve_kr",
    "run_panel_calc",
]

