from nlp.classifier import train_model

if __name__ == "__main__":
    train_model()
    print("Modelo TF-IDF híbrido + Regressão Logística salvo em models/classifier.joblib")
