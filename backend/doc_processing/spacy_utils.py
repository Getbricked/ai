import os
import json
import sys
import logging
import subprocess
from typing import Optional, List

import spacy
from spacy.util import is_package

logger = logging.getLogger(__name__)

_nlp: Optional[spacy.language.Language] = None

DEFAULT_MODEL = "en_core_web_sm"
DEFAULT_BATCH_SIZE = 100


def _ensure_model(model: str) -> None:
    if not is_package(model):
        logger.info("Downloading spaCy model '%s'...", model)
        subprocess.check_call([sys.executable, "-m", "spacy", "download", model])
        logger.info("Successfully downloaded '%s'.", model)


def get_nlp(model: str = DEFAULT_MODEL) -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        _ensure_model(model)
        logger.info("Loading spaCy model '%s'...", model)
        _nlp = spacy.load(model)
    return _nlp


def _compress_doc(text: str) -> str:
    return " ".join(
        token.lemma_
        for token in text
        if not token.is_stop
        and not token.is_punct
        and not token.is_space
        and token.is_alpha
    )


def compress_text(text: str, model: str = DEFAULT_MODEL) -> str:
    if not text or not text.strip():
        return text
    nlp = get_nlp(model)
    doc = nlp(text)
    return _compress_doc(doc)


def compress_texts_batch(
    texts: List[str],
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> List[str]:
    nlp = get_nlp(model)
    results = []
    for doc in nlp.pipe(texts, batch_size=batch_size):
        if doc.text.strip():
            results.append(_compress_doc(doc))
        else:
            results.append(doc.text)
    return results


def process_text_for_embedding(text: str, model: str = DEFAULT_MODEL) -> str:
    return compress_text(text, model)


def process_backup_json(
    backup_dir: Optional[str] = None,
    out_dir: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
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

    files = sorted(f for f in os.listdir(backup_dir) if f.endswith(".json"))
    if not files:
        logger.info("No JSON files in '%s'.", backup_dir)
        return

    logger.info("Reading %d JSON files from '%s'...", len(files), backup_dir)
    entries = []
    for name in files:
        path = os.path.join(backup_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries.append((name, data))
        except Exception as e:
            logger.error("Failed to read '%s': %s", name, e)

    texts_to_compress = []
    text_indices = []
    for idx, (name, data) in enumerate(entries):
        content = data.get("content", "")
        if content.strip():
            texts_to_compress.append(content)
            text_indices.append(idx)

    if not texts_to_compress:
        logger.info("No documents with content to compress.")
        return

    logger.info(
        "Compressing %d documents in batches of %d...",
        len(texts_to_compress),
        batch_size,
    )

    compressed = compress_texts_batch(texts_to_compress, model, batch_size)

    logger.info("Writing %d compressed files to '%s'...", len(entries), out_dir)
    compressed_iter = iter(compressed)
    for idx, (name, data) in enumerate(entries):
        out_path = os.path.join(out_dir, name)
        try:
            content = data.get("content", "")
            if content.strip():
                data["content"] = next(compressed_iter)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to write '%s': %s", name, e)


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
    parser.add_argument(
        "--text", type=str, default=None, help="Compress a single text string"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL, help="spaCy model name"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Batch size for nlp.pipe (default: 64)",
    )

    args = parser.parse_args()

    if args.text:
        print(compress_text(args.text, args.model))
    elif args.backup:
        kwargs = {"model": args.model, "batch_size": args.batch_size}
        if args.backup == "default":
            process_backup_json(out_dir=args.out, **kwargs)
        else:
            process_backup_json(args.backup, out_dir=args.out, **kwargs)
    else:
        parser.print_help()
