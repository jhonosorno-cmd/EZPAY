"""Configuración del módulo de voz para el MVP. Se cambia aquí sin tocar el código."""
from pathlib import Path

from voice.amounts import AssetConfig

ASSET = AssetConfig("COP", 2)
# Palabra que se dice después de un monto, por assetCode (decisión de Sebastián: no va en la plantilla).
CURRENCY_WORDS = {"COP": "pesos"}
# Agenda PROVISIONAL y ficticia: se reemplaza por la que entregue Pagos.
AGENDA_PATH = Path(__file__).with_name("agenda_provisional.json")

# Transcripción de voz (speech-transcription, H2). Segundos enteros: el paquete no usa float.
AUDIO_MAX_DURATION_S = 30  # se lee de la cabecera antes de decodificar; más -> AUDIO_TOO_LONG
REMOTE_TIMEOUT_S = 3       # plazo del proveedor externo (Groq); lo aplica el motor real (Fase 2)
TURN_BUDGET_S = 8          # plazo del turno; un retry-after que no cabe -> respaldo local
MAX_REMOTE_ATTEMPTS = 2    # intento inicial más un reintento si el retry-after cabe en el plazo
