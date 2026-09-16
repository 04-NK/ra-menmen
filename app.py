import hmac
import json
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

from database import (
    DatabaseNotConfiguredError,
    create_place,
    create_places,
    delete_places,
    get_all_places,
    get_published_places,
)

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
MAX_JSON_FILE_SIZE = 1_000_000
MAX_JSON_PLACES = 100
JSON_TEMPLATE = {
    "places": [
        {
            "name": "場所の名前",
            "category": "restaurant",
            "latitude": 35.6476856,
            "longitude": 140.0354964,
            "description": "場所の説明",
            "price_level": 2,
            "address": "千葉県千葉市美浜区",
            "website_url": "https://example.com",
            "source_url": "https://example.com/source",
            "last_verified_at": None,
            "is_published": True,
        }
    ]
}


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


def get_text(data, field):
    value = data.get(field)

    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field}は文字列で入力してください")

    return value.strip()


def parse_place_data(data):
    if not isinstance(data, dict):
        raise ValueError("場所の情報はJSONオブジェクトで入力してください")

    name = get_text(data, "name")
    category = get_text(data, "category")
    category_values = {value for value, _ in CATEGORIES}

    if not name:
        raise ValueError("場所の名前を入力してください")
    if category not in category_values:
        raise ValueError("カテゴリを選択してください")

    try:
        if isinstance(data.get("latitude"), bool) or isinstance(
            data.get("longitude"), bool
        ):
            raise ValueError
        latitude = float(data.get("latitude", ""))
        longitude = float(data.get("longitude", ""))
    except (TypeError, ValueError) as error:
        raise ValueError("緯度と経度を数字で入力してください") from error

    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("緯度または経度の範囲が正しくありません")

    try:
        price_level_value = data.get("price_level")
        if isinstance(price_level_value, bool) or not isinstance(
            price_level_value, (int, str, type(None))
        ):
            raise ValueError
        price_level = (
            int(price_level_value)
            if price_level_value not in (None, "")
            else None
        )
    except (TypeError, ValueError) as error:
        raise ValueError("価格帯を選択してください") from error

    if price_level not in {None, 1, 2, 3}:
        raise ValueError("価格帯を選択してください")

    try:
        verified_value = get_text(data, "last_verified_at")
        last_verified_at = (
            date.fromisoformat(verified_value) if verified_value else None
        )
    except ValueError as error:
        raise ValueError("確認日を正しく入力してください") from error

    website_url = get_text(data, "website_url") or None
    source_url = get_text(data, "source_url") or None

    for value in (website_url, source_url):
        parsed_url = urlparse(value) if value else None
        if parsed_url and (
            parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc
        ):
            raise ValueError("URLは http:// または https:// から入力してください")

    is_published = data.get("is_published", False)
    if not isinstance(is_published, bool):
        raise ValueError("is_publishedは true または false で入力してください")

    return {
        "name": name,
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
        "description": get_text(data, "description") or None,
        "price_level": price_level,
        "address": get_text(data, "address") or None,
        "website_url": website_url,
        "source_url": source_url,
        "last_verified_at": last_verified_at,
        "is_published": is_published,
    }


def parse_place_form(form):
    data = form.to_dict()
    data["is_published"] = form.get("is_published") == "on"
    return parse_place_data(data)


def parse_places_json(upload):
    if not upload or not upload.filename:
        raise ValueError("JSONファイルを選択してください")

    file_data = upload.stream.read(MAX_JSON_FILE_SIZE + 1)
    if len(file_data) > MAX_JSON_FILE_SIZE:
        raise ValueError("JSONファイルは1MB以下にしてください")

    try:
        payload = json.loads(file_data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("JSONファイルの形式が正しくありません") from error

    raw_places = payload.get("places") if isinstance(payload, dict) else payload
    if not isinstance(raw_places, list):
        raise ValueError('JSONは配列または {"places": [...]} の形式にしてください')
    if not raw_places:
        raise ValueError("JSONに場所が含まれていません")
    if len(raw_places) > MAX_JSON_PLACES:
        raise ValueError(f"一度に登録できるのは{MAX_JSON_PLACES}件までです")

    places = []
    for index, raw_place in enumerate(raw_places, start=1):
        try:
            places.append(parse_place_data(raw_place))
        except ValueError as error:
            raise ValueError(f"{index}件目: {error}") from error

    return places


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


def render_admin_page(
    error=None,
    import_error=None,
    delete_error=None,
    form=None,
    is_post=False,
):
    list_error = None

    try:
        registered_places = get_all_places()
    except DatabaseNotConfiguredError:
        registered_places = []
        list_error = "データベースが設定されていません"
    except psycopg.Error:
        app.logger.exception("場所の一覧を取得できませんでした")
        registered_places = []
        list_error = "場所の一覧を取得できませんでした"

    return render_template(
        "admin_places.html",
        categories=CATEGORIES,
        category_labels=dict(CATEGORIES),
        delete_error=delete_error,
        error=error,
        form=form or {},
        deleted_count=request.args.get("deleted", type=int),
        imported_count=request.args.get("imported", type=int),
        import_error=import_error,
        is_post=is_post,
        json_template=json.dumps(JSON_TEMPLATE, ensure_ascii=False, indent=2),
        list_error=list_error,
        places=registered_places,
        success=request.args.get("created") is not None,
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

    return render_admin_page(
        error=error,
        form=request.form,
        is_post=request.method == "POST",
    )


# JSONファイルから場所をまとめて登録する
@app.post("/admin/places/import")
@admin_required
def import_places():
    try:
        places_to_create = parse_places_json(request.files.get("json_file"))
        imported_count = create_places(places_to_create)
    except (ValueError, DatabaseNotConfiguredError) as exception:
        error = str(exception) or "データベースが設定されていません"
        return render_admin_page(import_error=error)
    except psycopg.Error:
        app.logger.exception("JSONから場所を登録できませんでした")
        return render_admin_page(import_error="JSONから場所を登録できませんでした")

    return redirect(url_for("admin_places", imported=imported_count))


# 一覧で選択された場所をまとめて削除する
@app.post("/admin/places/delete")
@admin_required
def remove_places():
    try:
        raw_ids = request.form.getlist("place_ids")
        place_ids = list(dict.fromkeys(int(place_id) for place_id in raw_ids))

        if (
            not place_ids
            or len(place_ids) > 500
            or any(place_id <= 0 for place_id in place_ids)
        ):
            raise ValueError("削除する場所を選択してください")

        deleted_count = delete_places(place_ids)
    except ValueError:
        return render_admin_page(delete_error="削除する場所を選択してください")
    except DatabaseNotConfiguredError:
        return render_admin_page(delete_error="データベースが設定されていません")
    except psycopg.Error:
        app.logger.exception("場所を削除できませんでした")
        return render_admin_page(delete_error="場所を削除できませんでした")

    return redirect(url_for("admin_places", deleted=deleted_count))


# python app.py で直接起動するときに実行
if __name__ == "__main__":
    app.run()
