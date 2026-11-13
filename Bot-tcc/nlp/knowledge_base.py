"""Recuperação semântica controlada das perguntas acadêmicas revisadas."""
from pathlib import Path
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .preprocess import normalize_text

DATA_PATH = Path(__file__).resolve().parent.parent / "database" / "qa_training.json"
with DATA_PATH.open(encoding="utf-8") as file:
    ENTRIES = json.load(file)["entradas"]

_TEXTS = [normalize_text(item["pergunta"]) for item in ENTRIES]
_VECTORIZER = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
_MATRIX = _VECTORIZER.fit_transform(_TEXTS)


def retrieve(message: str, threshold: float = 0.82):
    """Retorna a entrada controlada mais próxima quando a similaridade é suficiente."""
    normalized = normalize_text(message)
    if not normalized:
        return None
    vector = _VECTORIZER.transform([normalized])
    scores = cosine_similarity(vector, _MATRIX)[0]
    index = int(scores.argmax())
    score = float(scores[index])
    if score < threshold:
        return None
    item = dict(ENTRIES[index])
    item["similaridade"] = round(score, 4)
    item["texto_normalizado"] = normalized
    return item


def count():
    return len(ENTRIES)
