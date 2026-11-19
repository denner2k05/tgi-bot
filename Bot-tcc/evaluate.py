"""Avalia os classificadores com validação cruzada estratificada.

A avaliação não representa um teste com alunos reais. As métricas são obtidas
por previsões out-of-fold: cada exemplo é avaliado por um modelo que não o
utilizou no treinamento daquele fold.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from nlp.classifier import training_data


N_SPLITS = 5
RANDOM_STATE = 42


def _models():
    return {
        "regressao_logistica": LogisticRegression(max_iter=2000, solver="liblinear"),
        "naive_bayes": MultinomialNB(),
        "svm": LinearSVC(),
        "regressao_logistica_tfidf_hibrido": Pipeline([
            ("features", FeatureUnion([
                ("palavras", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                ("caracteres", TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
                )),
            ])),
            ("clf", LogisticRegression(
                max_iter=3000, solver="liblinear", class_weight="balanced"
            )),
        ]),
    }


def evaluate():
    texts, labels = training_data()
    cv = StratifiedKFold(
        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
    )
    labels_order = sorted(set(labels))
    results = {}

    for name, estimator in _models().items():
        pipe = estimator if isinstance(estimator, Pipeline) else Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("clf", estimator),
        ])
        predictions = cross_val_predict(pipe, texts, labels, cv=cv, method="predict")
        results[name] = {
            "metrics": classification_report(
                labels, predictions, output_dict=True, zero_division=0
            ),
            "labels": labels_order,
            "confusion_matrix": confusion_matrix(
                labels, predictions, labels=labels_order
            ).tolist(),
            "protocol": {
                "type": "stratified_k_fold_out_of_fold",
                "n_splits": N_SPLITS,
                "random_state": RANDOM_STATE,
                "examples": len(texts),
                "intents": len(labels_order),
            },
        }
    return results


if __name__ == "__main__":
    for name, report in evaluate().items():
        metrics = report["metrics"]
        print(
            name,
            "accuracy=", round(metrics["accuracy"], 3),
            "macro_precision=", round(metrics["macro avg"]["precision"], 3),
            "macro_recall=", round(metrics["macro avg"]["recall"], 3),
            "macro_f1=", round(metrics["macro avg"]["f1-score"], 3),
        )
