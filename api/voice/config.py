"""Configuración del módulo de voz para el MVP. Se cambia aquí sin tocar el código."""
from pathlib import Path

from voice.amounts import AssetConfig

ASSET = AssetConfig("COP", 2)
# Palabra que se dice después de un monto, por assetCode (decisión de Sebastián: no va en la plantilla).
CURRENCY_WORDS = {"COP": "pesos"}
# Agenda PROVISIONAL y ficticia: se reemplaza por la que entregue Pagos.
AGENDA_PATH = Path(__file__).with_name("agenda_provisional.json")
