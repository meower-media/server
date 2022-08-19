from flask import Flask, request

app = Flask(__name__)

@app.route('/', methods=["POST"])
def upload_attatchment():
    print(request.files['file'])
    return "hi"

app.run(host="0.0.0.0", port=3002, debug=True)