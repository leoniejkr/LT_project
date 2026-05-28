import os
from flask import Flask, jsonify

app = Flask(__name__)

# Prüfen, ob wir im Mock-Modus sind (Standardmäßig Ja)
USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"

if USE_MOCK:
    from mock_service import register_mock_routes
    register_mock_routes(app)
    print("Running in MOCK mode")
else:
    # Hier kommt später die echte Implementierung rein
    @app.route('/predict', methods=['POST'])
    def predict():
        # TODO: Echte LLM Logik hier
        return jsonify({"status": "error", "message": "Real LLM not implemented yet"}), 501
    print("Running in PRODUCTION mode")

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "mode": "mock" if USE_MOCK else "production"
    })

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
