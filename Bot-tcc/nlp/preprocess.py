"""Pré-processamento leve e reproduzível para perguntas em português."""
import re
import unicodedata

STOPWORDS = {"a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "e", "é", "que", "qual", "como", "meu", "minha", "minhas", "me", "para"}


def normalize_text(text: str) -> str:
    """Converte entrada em tokens normalizados, mantendo conteúdo útil."""
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [token for token in text.split() if token not in STOPWORDS]
    return " ".join(tokens)
