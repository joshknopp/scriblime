from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    notification = request.json
    # Process the notification here
    print(notification)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
