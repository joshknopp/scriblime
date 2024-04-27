from flask import Flask, request, jsonify
import main

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    notification = request.json
    main.process_notification(notification)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
