"""Treinamento e inferência do classificador de intenções."""
from pathlib import Path
import json
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC
from .intents import INTENTS
from .preprocess import normalize_text

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODEL_DIR / "classifier.joblib"


def training_data():
    texts, labels = [], []
    for label, examples in INTENTS.items():
        for example in examples:
            texts.append(normalize_text(example))
            labels.append(label)
    return texts, labels


def train_model():
    texts, labels = training_data()
    features = FeatureUnion([
        ("palavras", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
        ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
    ])
    model = Pipeline([("tfidf_hibrido", features), ("clf", LogisticRegression(max_iter=3000, solver="liblinear", class_weight="balanced"))])
    model.fit(texts, labels)
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    return model


def load_model():
    if not MODEL_PATH.exists():
        return train_model()
    return joblib.load(MODEL_PATH)


def predict(text: str):
    model = load_model()
    normalized = normalize_text(text)
    if not normalized:
        return {"intent": "fallback", "confidence": 0.0, "normalized": normalized}
    probabilities = model.predict_proba([normalized])[0]
    index = probabilities.argmax()
    intent = model.classes_[index]
    confidence = float(probabilities[index])
    # O conjunto acadêmico inicial possui muitas intenções e poucos exemplos por classe.
    # O limiar é deliberadamente conservador, mas permite intenções dominantes como
    # endereço, horário e nota; entradas sem sinal suficiente continuam em fallback.
    if confidence < 0.07:
        intent = "fallback"
    return {"intent": intent, "confidence": round(confidence, 4), "normalized": normalized}
