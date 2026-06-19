import os
import json
import sys
import logging
import subprocess
from typing import Optional

import spacy
from spacy.util import is_package

logger = logging.getLogger(__name__)

_nlp: Optional[spacy.language.Language] = None

DEFAULT_MODEL = "en_core_web_sm"


def _ensure_model(model: str) -> None:
    if not is_package(model):
        logger.info("Downloading spaCy model '%s'...", model)
        subprocess.check_call(
            [sys.executable, "-m", "spacy", "download", model]
        )
        logger.info("Successfully downloaded '%s'.", model)


def get_nlp(model: str = DEFAULT_MODEL) -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        _ensure_model(model)
        logger.info("Loading spaCy model '%s'...", model)
        _nlp = spacy.load(model)
    return _nlp


def compress_text(text: str, model: str = DEFAULT_MODEL) -> str:
    if not text or not text.strip():
        return text
    nlp = get_nlp(model)
    doc = nlp(text)
    tokens = [
        token.lemma_
        for token in doc
        if not token.is_stop and not token.is_punct and not token.is_space and token.is_alpha
    ]
    return " ".join(tokens)


def process_text_for_embedding(text: str, model: str = DEFAULT_MODEL) -> str:
    return compress_text(text, model)


def process_backup_json(
    backup_dir: Optional[str] = None,
    out_dir: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> None:
    if backup_dir is None:
        backup_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "backup")
        )

    if out_dir is None:
        out_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "backup-compressed")
        )

    if not os.path.isdir(backup_dir):
        logger.error("Backup directory '%s' not found.", backup_dir)
        return

    os.makedirs(out_dir, exist_ok=True)

    files = [f for f in os.listdir(backup_dir) if f.endswith(".json")]
    if not files:
        logger.info("No JSON files in '%s'.", backup_dir)
        return

    logger.info("Processing %d JSON files from '%s' -> '%s'...", len(files), backup_dir, out_dir)
    for name in files:
        path = os.path.join(backup_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            original = data.get("content", "")
            if not original.strip():
                out_path = os.path.join(out_dir, name)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info("Copied '%s' (empty content)", name)
                continue

            compressed = compress_text(original, model)

            data["content"] = compressed

            out_path = os.path.join(out_dir, name)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Compressed '%s'", name)
        except Exception as e:
            logger.error("Failed to process '%s': %s", name, e)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Compress text with spaCy")
    parser.add_argument(
        "--backup",
        type=str,
        default=None,
        help="Process JSON files in backup directory (path or 'default')",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output directory for compressed files (default: backup-compressed/)",
    )
    parser.add_argument("--text", type=str, default=None, help="Compress a single text string")
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL, help="spaCy model name"
    )

    args = parser.parse_args()

    if args.text:
        print(compress_text(args.text, args.model))
    elif args.backup:
        if args.backup == "default":
            process_backup_json(model=args.model, out_dir=args.out)
        else:
            process_backup_json(args.backup, out_dir=args.out, model=args.model)
    else:
        parser.print_help()
