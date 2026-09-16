from flask import Flask, render_template

app = Flask(__name__)


# トップ画面
@app.get("/")
def index():
    return render_template("index.html")


# 「はじめる」から進む地図画面
@app.get("/app")
def main():
    return render_template("app.html")


# python app.py で直接起動するときに実行
if __name__ == "__main__":
    app.run()
