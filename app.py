import hmac
import json
import os
import re
from datetime import date, datetime, time
from functools import wraps
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

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
    create_category,
    create_place,
    create_places,
    delete_places,
    get_all_places,
    get_categories,
    get_place,
    get_published_places,
    update_place,
)

app = Flask(__name__)

WEEKDAYS = (
    ("monday", "月曜日"),
    ("tuesday", "火曜日"),
    ("wednesday", "水曜日"),
    ("thursday", "木曜日"),
    ("friday", "金曜日"),
    ("saturday", "土曜日"),
    ("sunday", "日曜日"),
)
WEEKDAY_KEYS = {key for key, _ in WEEKDAYS}
MAX_JSON_FILE_SIZE = 1_000_000
MAX_JSON_PLACES = 100
JAPAN_TIME_ZONE = ZoneInfo("Asia/Tokyo")
JSON_TEMPLATE = {
    "places": [
        {
            "name": "場所の名前",
            "category": "restaurant",
            "latitude": 35.6476856,
            "longitude": 140.0354964,
            "description": "場所の説明",
            "opening_hours": {
                "monday": [
                    {"open": "11:00", "close": "14:00"},
                    {"open": "17:00", "close": "21:00"},
                ],
                "tuesday": None,
                "wednesday": [{"open": "11:00", "close": "21:00"}],
                "thursday": [{"open": "11:00", "close": "21:00"}],
                "friday": [{"open": "11:00", "close": "21:00"}],
                "saturday": [{"open": "10:00", "close": "21:00"}],
                "sunday": [{"open": "10:00", "close": "20:00"}],
            },
            "closed_dates": ["2026-09-20"],
            "annual_closed_dates": ["01-01", "12-31"],
            "recurring_closed_days": [
                {"week_of_month": 2, "day": "tuesday"},
                {"week_of_month": 4, "day": "tuesday"},
            ],
            "price_min": 800,
            "price_max": 1200,
            "address": "千葉県千葉市美浜区",
            "website_url": "https://example.com",
            "source_url": "https://example.com/source",
            "last_verified_at": "2026-01-15",
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


def get_optional_price(data, field, label):
    value = data.get(field)

    if isinstance(value, str):
        value = value.strip()
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{label}は0以上の整数で入力してください")

    try:
        price = int(value)
    except ValueError as error:
        raise ValueError(f"{label}は0以上の整数で入力してください") from error

    if price < 0:
        raise ValueError(f"{label}は0以上の整数で入力してください")

    return price


def parse_clock(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label}を時刻で入力してください")

    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label}を時刻で入力してください") from error


def normalize_hours_periods(day_hours, label):
    if isinstance(day_hours, dict):
        return [day_hours]
    if isinstance(day_hours, list):
        return day_hours
    raise ValueError(f"{label}の営業時間が正しくありません")


def parse_hours_period(period, day_of_week, period_index, label):
    if not isinstance(period, dict):
        raise ValueError(f"{label}の営業時間が正しくありません")

    return {
        "day_of_week": day_of_week,
        "period_index": period_index,
        "opens_at": parse_clock(period.get("open"), f"{label}の開店時刻"),
        "closes_at": parse_clock(period.get("close"), f"{label}の閉店時刻"),
        "is_closed": False,
    }


def parse_opening_hours(data):
    raw_hours = data.get("opening_hours")

    if raw_hours is None:
        return []
    if not isinstance(raw_hours, dict):
        raise ValueError("opening_hoursは曜日ごとの形式で入力してください")

    unknown_keys = set(raw_hours) - WEEKDAY_KEYS
    if unknown_keys:
        raise ValueError(f"営業時間の曜日が正しくありません: {unknown_keys.pop()}")

    opening_hours = []
    for day_of_week, (key, label) in enumerate(WEEKDAYS):
        if key not in raw_hours:
            continue

        day_hours = raw_hours[key]
        if day_hours is None:
            opening_hours.append(
                {
                    "day_of_week": day_of_week,
                    "period_index": 0,
                    "opens_at": None,
                    "closes_at": None,
                    "is_closed": True,
                }
            )
            continue

        periods = normalize_hours_periods(day_hours, label)

        if not periods:
            continue
        if len(periods) > 10:
            raise ValueError(f"{label}の営業時間は10件以内で入力してください")

        for period_index, period in enumerate(periods):
            opening_hours.append(
                parse_hours_period(period, day_of_week, period_index, label)
            )

    return opening_hours


def parse_closed_dates(data):
    raw_dates = data.get("closed_dates")

    if raw_dates is None:
        return []
    if not isinstance(raw_dates, list):
        raise ValueError("closed_datesは日付の配列で入力してください")
    if len(raw_dates) > 100:
        raise ValueError("特定の休業日は100件以内で入力してください")

    closed_dates = set()
    for raw_date in raw_dates:
        if not isinstance(raw_date, str) or not raw_date.strip():
            raise ValueError("特定の休業日はYYYY-MM-DD形式で入力してください")
        try:
            closed_dates.add(date.fromisoformat(raw_date.strip()))
        except ValueError as error:
            raise ValueError(
                "特定の休業日はYYYY-MM-DD形式で入力してください"
            ) from error

    return sorted(closed_dates)


def parse_annual_closed_dates(data):
    raw_dates = data.get("annual_closed_dates")

    if raw_dates is None:
        return []
    if not isinstance(raw_dates, list):
        raise ValueError("annual_closed_datesは月日の配列で入力してください")
    if len(raw_dates) > 366:
        raise ValueError("毎年の休業日は366件以内で入力してください")

    annual_closed_dates = set()
    for raw_date in raw_dates:
        if not isinstance(raw_date, str) or not re.fullmatch(
            r"\d{2}-\d{2}", raw_date.strip()
        ):
            raise ValueError("毎年の休業日はMM-DD形式で入力してください")
        month, day = (int(value) for value in raw_date.split("-"))
        try:
            date(2000, month, day)
        except ValueError as error:
            raise ValueError("毎年の休業日に存在する月日を入力してください") from error
        annual_closed_dates.add((month, day))

    return [
        {"month": month, "day": day}
        for month, day in sorted(annual_closed_dates)
    ]


def parse_recurring_closed_days(data):
    raw_rules = data.get("recurring_closed_days")

    if raw_rules is None:
        return []
    if not isinstance(raw_rules, list):
        raise ValueError("recurring_closed_daysは配列で入力してください")
    if len(raw_rules) > 35:
        raise ValueError("毎月の定休日は35件以内で入力してください")

    weekday_indexes = {key: index for index, (key, _) in enumerate(WEEKDAYS)}
    recurring_closed_days = set()

    for rule in raw_rules:
        if not isinstance(rule, dict):
            raise ValueError("毎月の定休日の形式が正しくありません")

        week_of_month = rule.get("week_of_month")
        day = rule.get("day")
        if isinstance(week_of_month, bool):
            raise ValueError("毎月の定休日の週は1から5で入力してください")
        try:
            week_of_month = int(week_of_month)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "毎月の定休日の週は1から5で入力してください"
            ) from error
        if week_of_month not in range(1, 6):
            raise ValueError("毎月の定休日の週は1から5で入力してください")
        if day not in weekday_indexes:
            raise ValueError("毎月の定休日の曜日が正しくありません")

        recurring_closed_days.add((week_of_month, weekday_indexes[day]))

    return [
        {"week_of_month": week, "day_of_week": day}
        for week, day in sorted(recurring_closed_days)
    ]


def get_form_hour_values(form, key):
    return (
        form.getlist(f"hours_{key}_open"),
        form.getlist(f"hours_{key}_close"),
    )


def parse_opening_hours_form(form):
    opening_hours = {}

    for key, _ in WEEKDAYS:
        if form.get(f"hours_{key}_closed") == "on":
            opening_hours[key] = None
            continue

        opens_at_values, closes_at_values = get_form_hour_values(form, key)
        if len(opens_at_values) != len(closes_at_values):
            raise ValueError("営業時間の入力形式が正しくありません")
        periods = []

        for opens_at, closes_at in zip(opens_at_values, closes_at_values):
            opens_at = opens_at.strip()
            closes_at = closes_at.strip()
            if not opens_at and not closes_at:
                continue
            periods.append({"open": opens_at, "close": closes_at})

        if periods:
            opening_hours[key] = periods

    return opening_hours


def parse_closed_dates_form(form):
    return [value.strip() for value in form.getlist("closed_dates") if value.strip()]


def parse_annual_closed_dates_form(form):
    months = form.getlist("annual_closed_month")
    days = form.getlist("annual_closed_day")
    if len(months) != len(days):
        raise ValueError("毎年の休業日の入力形式が正しくありません")

    dates = []
    for month, day in zip(months, days):
        month = month.strip()
        day = day.strip()
        if not month and not day:
            continue
        if not month or not day:
            raise ValueError("毎年の休業日は月と日を入力してください")
        try:
            dates.append(f"{int(month):02d}-{int(day):02d}")
        except ValueError as error:
            raise ValueError("毎年の休業日は月と日を数字で入力してください") from error

    return dates


def parse_recurring_closed_days_form(form):
    weeks = form.getlist("recurring_closed_week")
    days = form.getlist("recurring_closed_day")
    if len(weeks) != len(days):
        raise ValueError("毎月の定休日の入力形式が正しくありません")

    rules = []
    for week, day in zip(weeks, days):
        week = week.strip()
        day = day.strip()
        if not week and not day:
            continue
        if not week or not day:
            raise ValueError("毎月の定休日は週と曜日を選択してください")
        rules.append({"week_of_month": week, "day": day})

    return rules


def closure_fields_from_form(form):
    closed_dates = [
        value.strip() for value in form.getlist("closed_dates") if value.strip()
    ]
    months = form.getlist("annual_closed_month")
    annual_days = form.getlist("annual_closed_day")
    annual_closed_dates = [
        {"month": month, "day": day}
        for month, day in zip(months, annual_days)
        if month or day
    ]
    weeks = form.getlist("recurring_closed_week")
    days = form.getlist("recurring_closed_day")
    recurring_closed_days = [
        {"week_of_month": week, "day": day}
        for week, day in zip(weeks, days)
        if week or day
    ]
    return closed_dates, annual_closed_dates, recurring_closed_days


def closures_to_form(place):
    closed_dates = [str(value) for value in place.get("closed_dates") or []]
    annual_closed_dates = [
        {"month": str(rule["month"]), "day": str(rule["day"])}
        for rule in place.get("annual_closed_dates") or []
    ]
    recurring_closed_days = [
        {
            "week_of_month": str(rule["week_of_month"]),
            "day": WEEKDAYS[rule["day_of_week"]][0],
        }
        for rule in place.get("recurring_closed_days") or []
    ]
    return closed_dates, annual_closed_dates, recurring_closed_days


def opening_hours_fields_from_form(form):
    form_hours = {}

    for key, _ in WEEKDAYS:
        opens_at_values, closes_at_values = get_form_hour_values(form, key)
        periods = [
            {"open": opens_at, "close": closes_at}
            for opens_at, closes_at in zip(opens_at_values, closes_at_values)
        ]
        form_hours[key] = {
            "periods": periods,
            "closed": form.get(f"hours_{key}_closed") == "on",
        }

    return form_hours


def opening_hours_to_form(opening_hours):
    form_hours = {}

    for hours in opening_hours:
        key = WEEKDAYS[hours["day_of_week"]][0]
        day_hours = form_hours.setdefault(
            key,
            {"periods": [], "closed": False},
        )
        if hours["is_closed"]:
            day_hours["closed"] = True
            continue

        day_hours["periods"].append(
            {
                "open": hours.get("opens_at") or "",
                "close": hours.get("closes_at") or "",
            }
        )

    return form_hours


def parse_place_data(data, category_values):
    if not isinstance(data, dict):
        raise ValueError("場所の情報はJSONオブジェクトで入力してください")

    name = get_text(data, "name")
    category = get_text(data, "category")

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

    price_min = get_optional_price(data, "price_min", "最低価格")
    price_max = get_optional_price(data, "price_max", "最高価格")
    if price_min is not None and price_max is not None and price_min > price_max:
        raise ValueError("最高価格は最低価格以上で入力してください")

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
        "opening_hours": parse_opening_hours(data),
        "closed_dates": parse_closed_dates(data),
        "annual_closed_dates": parse_annual_closed_dates(data),
        "recurring_closed_days": parse_recurring_closed_days(data),
        "price_min": price_min,
        "price_max": price_max,
        "address": get_text(data, "address") or None,
        "website_url": website_url,
        "source_url": source_url,
        "last_verified_at": last_verified_at,
        "is_published": is_published,
    }


def parse_place_form(form, category_values):
    data = form.to_dict()
    data["is_published"] = form.get("is_published") == "on"
    data["opening_hours"] = parse_opening_hours_form(form)
    data["closed_dates"] = parse_closed_dates_form(form)
    data["annual_closed_dates"] = parse_annual_closed_dates_form(form)
    data["recurring_closed_days"] = parse_recurring_closed_days_form(form)
    return parse_place_data(data, category_values)


def parse_places_json(upload, category_values):
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
            places.append(parse_place_data(raw_place, category_values))
        except ValueError as error:
            raise ValueError(f"{index}件目: {error}") from error

    return places


def get_category_choices(category_rows):
    return [
        (category["value"], category["display_name"])
        for category in category_rows
    ]


def get_category_values(category_rows):
    return {category["value"] for category in category_rows}


# トップ画面
@app.get("/")
def index():
    return render_template("index.html")


# 「はじめる」から進む地図画面
@app.get("/app")
def main():
    return render_template("app.html")


# DBから取得した時刻を比較できる形にそろえる
def parse_database_time(value):
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError:
            return None
    return None


# 曜日別の営業時間から、指定した時刻に営業中か判定する
def get_closed_reason(place, current_date):
    for closed_date in place.get("closed_dates") or []:
        if str(closed_date) == current_date.isoformat():
            return "臨時休業"

    for rule in place.get("annual_closed_dates") or []:
        if rule.get("month") == current_date.month and rule.get("day") == current_date.day:
            return "定休日"

    week_of_month = (current_date.day - 1) // 7 + 1
    for rule in place.get("recurring_closed_days") or []:
        if (
            rule.get("week_of_month") == week_of_month
            and rule.get("day_of_week") == current_date.weekday()
        ):
            return "定休日"

    return None


def is_within_opening_hours(place, current_datetime):
    current_day = current_datetime.weekday()
    current_time = current_datetime.time().replace(tzinfo=None)

    for hours in place.get("opening_hours") or []:
        if hours.get("is_closed"):
            continue

        opens_at = parse_database_time(hours.get("opens_at"))
        closes_at = parse_database_time(hours.get("closes_at"))
        if opens_at is None or closes_at is None:
            continue

        day_of_week = hours.get("day_of_week")
        if not isinstance(day_of_week, int):
            continue
        if opens_at < closes_at:
            if day_of_week == current_day and opens_at <= current_time < closes_at:
                return True
            continue

        # 閉店が開店以前なら、翌日にまたがる営業時間として扱う
        if day_of_week == current_day and current_time >= opens_at:
            return True
        if (day_of_week + 1) % 7 == current_day and current_time < closes_at:
            return True

    return False


def is_place_open(place, current_datetime):
    return not get_closed_reason(
        place, current_datetime.date()
    ) and is_within_opening_hours(place, current_datetime)


def add_open_status(place, current_datetime):
    place = dict(place)
    opening_hours = place.get("opening_hours") or []
    closed_reason = get_closed_reason(place, current_datetime.date())
    place["is_open_now"] = not closed_reason and is_within_opening_hours(
        place, current_datetime
    )

    if closed_reason:
        place["open_status"] = closed_reason
    elif not opening_hours:
        place["open_status"] = "営業時間未設定"
    elif place["is_open_now"]:
        place["open_status"] = "営業中"
    else:
        place["open_status"] = "営業時間外"

    return place


def price_sort_key(place):
    price_min = place.get("price_min")
    price_max = place.get("price_max")

    # 価格帯の中央額を基準にする。片方だけなら、その金額を使う。
    if price_min is not None and price_max is not None:
        price_center_twice = price_min + price_max
    elif price_min is not None:
        price_center_twice = price_min * 2
    elif price_max is not None:
        price_center_twice = price_max * 2
    else:
        price_center_twice = 0

    return (
        price_min is None and price_max is None,
        price_center_twice,
        price_min is None,
        price_min or 0,
        price_max is None,
        price_max or 0,
        place.get("name", ""),
    )


# 地図に表示する登録済みスポットを返す
@app.get("/api/places")
def places():
    try:
        current_datetime = datetime.now(JAPAN_TIME_ZONE)
        published_places = [
            add_open_status(place, current_datetime)
            for place in get_published_places()
        ]

        if request.args.get("open_now") == "1":
            published_places = [
                place for place in published_places if place["is_open_now"]
            ]

        published_places.sort(key=price_sort_key)

        return jsonify({"places": published_places})
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
    category_error=None,
    category_form=None,
    form=None,
    is_post=False,
):
    list_error = None

    if is_post and form is not None:
        (
            closed_dates_form,
            annual_closed_dates_form,
            recurring_closed_days_form,
        ) = closure_fields_from_form(form)
    else:
        closed_dates_form = []
        annual_closed_dates_form = []
        recurring_closed_days_form = []

    try:
        registered_places = get_all_places()
        category_rows = get_categories()
    except DatabaseNotConfiguredError:
        registered_places = []
        category_rows = []
        list_error = "データベースが設定されていません"
    except psycopg.Error:
        app.logger.exception("場所の一覧を取得できませんでした")
        registered_places = []
        category_rows = []
        list_error = "場所の一覧を取得できませんでした"

    category_choices = get_category_choices(category_rows)

    return render_template(
        "admin_places.html",
        categories=category_choices,
        category_created=request.args.get("category_created") is not None,
        category_error=category_error,
        category_form=category_form or {},
        delete_error=delete_error,
        error=error,
        form=form or {},
        deleted_count=request.args.get("deleted", type=int),
        imported_count=request.args.get("imported", type=int),
        import_error=import_error,
        is_post=is_post,
        is_published_checked=(
            not is_post or (form is not None and form.get("is_published") == "on")
        ),
        json_template=json.dumps(JSON_TEMPLATE, ensure_ascii=False, indent=2),
        list_error=list_error,
        closed_dates_form=closed_dates_form,
        annual_closed_dates_form=annual_closed_dates_form,
        recurring_closed_days_form=recurring_closed_days_form,
        opening_hours_form=(
            opening_hours_fields_from_form(form) if is_post and form is not None else {}
        ),
        places=registered_places,
        success=request.args.get("created") is not None,
        updated=request.args.get("updated") is not None,
        weekdays=WEEKDAYS,
    )


# 場所を登録する
@app.route("/admin/places", methods=["GET", "POST"])
@admin_required
def admin_places():
    error = None

    if request.method == "POST":
        try:
            category_values = get_category_values(get_categories())
            place = parse_place_form(request.form, category_values)
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


# 場所登録で使うカテゴリを追加する
@app.post("/admin/categories")
@admin_required
def add_category():
    value = request.form.get("value", "").strip()
    display_name = request.form.get("display_name", "").strip()

    try:
        if not display_name:
            raise ValueError("表示名を入力してください")
        if len(display_name) > 50:
            raise ValueError("表示名は50文字以内で入力してください")
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", value):
            raise ValueError(
                "DB用の値は40文字以内の半角英小文字・数字・_・-で入力してください"
            )
        if not create_category(value, display_name):
            raise ValueError("同じ表示名またはDB用の値が登録されています")
    except (ValueError, DatabaseNotConfiguredError) as exception:
        error = str(exception) or "データベースが設定されていません"
        return render_admin_page(
            category_error=error,
            category_form=request.form,
        )
    except psycopg.Error:
        app.logger.exception("カテゴリを追加できませんでした")
        return render_admin_page(
            category_error="カテゴリを追加できませんでした",
            category_form=request.form,
        )

    return redirect(url_for("admin_places", category_created=value))


# 登録済みの場所を編集する
@app.route("/admin/places/<int:place_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_place(place_id):
    try:
        place = get_place(place_id)
        category_rows = get_categories()
    except DatabaseNotConfiguredError:
        return "データベースが設定されていません", 503
    except psycopg.Error:
        app.logger.exception("編集する場所を取得できませんでした")
        return "編集する場所を取得できませんでした", 503

    if place is None:
        return "場所が見つかりません", 404

    category_choices = get_category_choices(category_rows)
    category_values = get_category_values(category_rows)

    error = None
    form = place
    is_published_checked = place["is_published"]
    opening_hours_form = opening_hours_to_form(place["opening_hours"])
    (
        closed_dates_form,
        annual_closed_dates_form,
        recurring_closed_days_form,
    ) = closures_to_form(place)

    if request.method == "POST":
        form = request.form
        is_published_checked = request.form.get("is_published") == "on"
        opening_hours_form = opening_hours_fields_from_form(request.form)
        (
            closed_dates_form,
            annual_closed_dates_form,
            recurring_closed_days_form,
        ) = closure_fields_from_form(request.form)

        try:
            updated_place = parse_place_form(request.form, category_values)
            updated_id = update_place(place_id, updated_place)
        except (ValueError, DatabaseNotConfiguredError) as exception:
            error = str(exception) or "データベースが設定されていません"
        except psycopg.Error:
            app.logger.exception("場所を更新できませんでした")
            error = "場所を更新できませんでした"
        else:
            if updated_id is None:
                return "場所が見つかりません", 404
            return redirect(url_for("admin_places", updated=updated_id))

    return render_template(
        "edit_place.html",
        categories=category_choices,
        closed_dates_form=closed_dates_form,
        error=error,
        annual_closed_dates_form=annual_closed_dates_form,
        form=form,
        is_published_checked=is_published_checked,
        opening_hours_form=opening_hours_form,
        recurring_closed_days_form=recurring_closed_days_form,
        weekdays=WEEKDAYS,
    )


# JSONファイルから場所をまとめて登録する
@app.post("/admin/places/import")
@admin_required
def import_places():
    try:
        category_values = get_category_values(get_categories())
        places_to_create = parse_places_json(
            request.files.get("json_file"),
            category_values,
        )
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
