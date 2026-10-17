"""Borra la huella del hablante y su consentimiento (PRIV-3).

Uso: python scripts/delete_voiceprint.py [--data-dir RUTA]
Por defecto usa EZPAY_SPEAKER_DATA_DIR o api/.data/speaker/.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # api/

from speaker.store import SpeakerStore


def main():
    parser = argparse.ArgumentParser(description="Delete the stored voice print and consent flag.")
    parser.add_argument("--data-dir", default=None,
                        help="Data directory (default: EZPAY_SPEAKER_DATA_DIR or api/.data/speaker/)")
    args = parser.parse_args()
    borrado = SpeakerStore(args.data_dir).delete()
    if borrado:
        print("Voice print and consent deleted.")
    else:
        print("No voice print was stored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())