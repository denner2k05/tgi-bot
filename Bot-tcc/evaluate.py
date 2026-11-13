"""Avalia modelos técnicos; não representa teste com alunos."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from nlp.classifier import training_data


def evaluate():
    texts, labels = training_data()
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts, labels, test_size=0.50, random_state=42, stratify=labels
    )
    models = {
        "regressao_logistica": LogisticRegression(max_iter=2000, solver="liblinear"),
        "naive_bayes": MultinomialNB(),
        "svm": LinearSVC(),
        "regressao_logistica_tfidf_hibrido": Pipeline([
            ("features", FeatureUnion([
                ("palavras", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
            ])),
            ("clf", LogisticRegression(max_iter=3000, solver="liblinear", class_weight="balanced")),
        ]),
    }
    results = {}
    for name, estimator in models.items():
        pipe = estimator if isinstance(estimator, Pipeline) else Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2))), ("clf", estimator)])
        pipe.fit(train_texts, train_labels)
        predictions = pipe.predict(test_texts)
        labels_order = sorted(set(labels))
        results[name] = {
            "metrics": classification_report(test_labels, predictions, output_dict=True, zero_division="warn"),
            "labels": labels_order,
            "confusion_matrix": confusion_matrix(test_labels, predictions, labels=labels_order).tolist(),
        }
    return results

if __name__ == "__main__":
    for name, report in evaluate().items():
        metrics = report["metrics"]
        print(name, "accuracy=", round(metrics["accuracy"], 3), "macro_precision=", round(metrics["macro avg"]["precision"], 3), "macro_recall=", round(metrics["macro avg"]["recall"], 3), "macro_f1=", round(metrics["macro avg"]["f1-score"], 3))
