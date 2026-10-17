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

# Motores reales (Fase 2). Ningún secreto: la llave solo vive en el entorno (GROQ_API_KEY).
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"
WHISPER_LOCAL_MODEL = "base"
SAMPLE_RATE = 16000              # PCM objetivo: float32, 16 kHz, mono (contrato-voz §4)
SPEECH_RMS_THRESHOLD = 0.015     # RMS mínimo de un tramo de 20 ms (PCM de -1 a 1); el ruido del cuarto medido llega a 0,009
SPEECH_MIN_SECONDS = 0.12        # los tramos con energía deben sumar al menos esto; menos: no hay habla (filtro previo)

# Desafío de confirmación por voz (confirmation-challenge, decidido el 17 oct).
CHALLENGE_BANK_PATH = Path(__file__).with_name("challenge_phrases.json")
CHALLENGE_MIN_MATCH = 0.80   # coincidencia mínima de la frase (1 - errores por palabra); se confirma con un experimento
CHALLENGE_MIN_PHRASES = 30
CHALLENGE_MIN_WORDS, CHALLENGE_MAX_WORDS = 6, 9
