import hmac
import os
from datetime import date
from functools import wraps
from urllib.parse import urlparse

import psycopg
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from database import DatabaseNotConfiguredError, create_place, get_published_places

app = Flask(__name__)

CATEGORIES = (
    ("restaurant", "レストラン"),
    ("cafe", "カフェ"),
    ("fast_food", "軽食"),
    ("shop", "お店"),
    ("tourism", "観光地"),
    ("park", "公園"),
    ("museum", "博物館・美術館"),
    ("other", "その他"),
)


# チーム用画面へのアクセスを確認する
def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        admin_password = os.getenv("ADMIN_PASSWORD")
        auth = request.authorization

        if not admin_password:
            return "ADMIN_PASSWORDが設定されていません", 503

        is_valid = (
            auth
            and hmac.compare_digest(auth.username or "", "ramenmen")
            and hmac.compare_digest(auth.password or "", admin_password)
        )

        if not is_valid:
            return Response(
                "認証が必要です",
                401,
                {"WWW-Authenticate": 'Basic realm="Yoritabi Admin"'},
            )

        return view(*args, **kwargs)

    return wrapped_view


def parse_place_form(form):
    name = form.get("name", "").strip()
    category = form.get("category", "").strip()
    category_values = {value for value, _ in CATEGORIES}

    if not name:
        raise ValueError("場所の名前を入力してください")
    if category not in category_values:
        raise ValueError("カテゴリを選択してください")

    try:
        latitude = float(form.get("latitude", ""))
        longitude = float(form.get("longitude", ""))
    except ValueError as error:
        raise ValueError("緯度と経度を数字で入力してください") from error

    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("緯度または経度の範囲が正しくありません")

    try:
        price_level_value = form.get("price_level", "").strip()
        price_level = int(price_level_value) if price_level_value else None
    except ValueError as error:
        raise ValueError("価格帯を選択してください") from error

    if price_level not in {None, 1, 2, 3}:
        raise ValueError("価格帯を選択してください")

    try:
        verified_value = form.get("last_verified_at", "").strip()
        last_verified_at = (
            date.fromisoformat(verified_value) if verified_value else None
        )
    except ValueError as error:
        raise ValueError("確認日を正しく入力してください") from error

    website_url = form.get("website_url", "").strip() or None
    source_url = form.get("source_url", "").strip() or None

    for value in (website_url, source_url):
        parsed_url = urlparse(value) if value else None
        if parsed_url and (
            parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc
        ):
            raise ValueError("URLは http:// または https:// から入力してください")

    return {
        "name": name,
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
        "description": form.get("description", "").strip() or None,
        "price_level": price_level,
        "address": form.get("address", "").strip() or None,
        "website_url": website_url,
        "source_url": source_url,
        "last_verified_at": last_verified_at,
        "is_published": form.get("is_published") == "on",
    }


# トップ画面
@app.get("/")
def index():
    return render_template("index.html")


# 「はじめる」から進む地図画面
@app.get("/app")
def main():
    return render_template("app.html")


# 地図に表示する登録済みスポットを返す
@app.get("/api/places")
def places():
    try:
        return jsonify({"places": get_published_places()})
    except DatabaseNotConfiguredError:
        return jsonify({"error": "データベースが設定されていません", "places": []}), 503
    except psycopg.Error:
        app.logger.exception("スポット情報を取得できませんでした")
        return (
            jsonify({"error": "スポット情報を取得できませんでした", "places": []}),
            503,
        )


# 場所を登録する
@app.route("/admin/places", methods=["GET", "POST"])
@admin_required
def admin_places():
    error = None

    if request.method == "POST":
        try:
            place = parse_place_form(request.form)
            place_id = create_place(place)
        except (ValueError, DatabaseNotConfiguredError) as exception:
            error = str(exception) or "データベースが設定されていません"
        except psycopg.Error:
            app.logger.exception("場所を登録できませんでした")
            error = "場所を登録できませんでした"
        else:
            return redirect(url_for("admin_places", created=place_id))

    return render_template(
        "admin_places.html",
        categories=CATEGORIES,
        error=error,
        form=request.form,
        is_post=request.method == "POST",
        success=request.args.get("created") is not None,
    )


# python app.py で直接起動するときに実行
if __name__ == "__main__":
    app.run()
