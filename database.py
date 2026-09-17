import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()

INSERT_PLACE_SQL = """
    INSERT INTO public.places (
        name,
        category,
        latitude,
        longitude,
        description,
        price_min,
        price_max,
        address,
        website_url,
        source_url,
        last_verified_at,
        is_published
    )
    VALUES (
        %(name)s,
        %(category)s,
        %(latitude)s,
        %(longitude)s,
        %(description)s,
        %(price_min)s,
        %(price_max)s,
        %(address)s,
        %(website_url)s,
        %(source_url)s,
        %(last_verified_at)s,
        %(is_published)s
    )
    RETURNING id
"""

OPENING_HOURS_SELECT_SQL = """
    COALESCE(
        (
            SELECT json_agg(
                json_build_object(
                    'day_of_week', hours.day_of_week,
                    'period_index', hours.period_index,
                    'opens_at', to_char(hours.opens_at, 'HH24:MI'),
                    'closes_at', to_char(hours.closes_at, 'HH24:MI'),
                    'is_closed', hours.is_closed
                )
                ORDER BY hours.day_of_week, hours.period_index
            )
            FROM public.place_opening_hours AS hours
            WHERE hours.place_id = places.id
        ),
        '[]'::json
    ) AS opening_hours
"""

CLOSED_DATES_SELECT_SQL = """
    COALESCE(
        (
            SELECT json_agg(to_char(closed_dates.closed_on, 'YYYY-MM-DD') ORDER BY closed_dates.closed_on)
            FROM public.place_closed_dates AS closed_dates
            WHERE closed_dates.place_id = places.id
        ),
        '[]'::json
    ) AS closed_dates
"""

ANNUAL_CLOSED_DATES_SELECT_SQL = """
    COALESCE(
        (
            SELECT json_agg(
                json_build_object(
                    'month', annual_closures.month,
                    'day', annual_closures.day
                )
                ORDER BY annual_closures.month, annual_closures.day
            )
            FROM public.place_annual_closures AS annual_closures
            WHERE annual_closures.place_id = places.id
        ),
        '[]'::json
    ) AS annual_closed_dates
"""

RECURRING_CLOSED_DAYS_SELECT_SQL = """
    COALESCE(
        (
            SELECT json_agg(
                json_build_object(
                    'week_of_month', recurring_closures.week_of_month,
                    'day_of_week', recurring_closures.day_of_week
                )
                ORDER BY recurring_closures.week_of_month, recurring_closures.day_of_week
            )
            FROM public.place_recurring_closures AS recurring_closures
            WHERE recurring_closures.place_id = places.id
        ),
        '[]'::json
    ) AS recurring_closed_days
"""


class DatabaseNotConfiguredError(RuntimeError):
    pass


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise DatabaseNotConfiguredError

    return database_url


def connect_database():
    return psycopg.connect(
        get_database_url(),
        connect_timeout=10,
        row_factory=dict_row,
    )


def save_opening_hours(cursor, place_id, opening_hours):
    if not opening_hours:
        return

    rows = [
        {
            **hours,
            "place_id": place_id,
        }
        for hours in opening_hours
    ]
    cursor.executemany(
        """
        INSERT INTO public.place_opening_hours (
            place_id,
            day_of_week,
            period_index,
            opens_at,
            closes_at,
            is_closed
        )
        VALUES (
            %(place_id)s,
            %(day_of_week)s,
            %(period_index)s,
            %(opens_at)s,
            %(closes_at)s,
            %(is_closed)s
        )
        """,
        rows,
    )


def save_closures(cursor, place_id, place):
    if place["closed_dates"]:
        cursor.executemany(
            """
            INSERT INTO public.place_closed_dates (place_id, closed_on)
            VALUES (%(place_id)s, %(closed_on)s)
            """,
            [
                {"place_id": place_id, "closed_on": closed_on}
                for closed_on in place["closed_dates"]
            ],
        )

    if place["annual_closed_dates"]:
        cursor.executemany(
            """
            INSERT INTO public.place_annual_closures (place_id, month, day)
            VALUES (%(place_id)s, %(month)s, %(day)s)
            """,
            [
                {"place_id": place_id, **rule}
                for rule in place["annual_closed_dates"]
            ],
        )

    if place["recurring_closed_days"]:
        cursor.executemany(
            """
            INSERT INTO public.place_recurring_closures (
                place_id,
                week_of_month,
                day_of_week
            )
            VALUES (%(place_id)s, %(week_of_month)s, %(day_of_week)s)
            """,
            [
                {"place_id": place_id, **rule}
                for rule in place["recurring_closed_days"]
            ],
        )


def insert_place(cursor, place):
    cursor.execute(INSERT_PLACE_SQL, place)
    place_id = cursor.fetchone()["id"]
    save_opening_hours(cursor, place_id, place["opening_hours"])
    save_closures(cursor, place_id, place)
    return place_id


def get_categories():
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT value, display_name, color, icon_name
                FROM public.place_categories
                ORDER BY display_order, created_at, value
                """
            )
            return cursor.fetchall()


def create_category(value, display_name, color, icon_name):
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.place_categories (
                    value,
                    display_name,
                    color,
                    icon_name
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING value
                """,
                (value, display_name, color, icon_name),
            )
            return cursor.fetchone() is not None


def update_category(value, display_name, color, icon_name):
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.place_categories
                SET
                    display_name = %s,
                    color = %s,
                    icon_name = %s
                WHERE value = %s
                RETURNING value
                """,
                (display_name, color, icon_name, value),
            )
            return cursor.fetchone() is not None


def get_published_places():
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    places.id,
                    places.name,
                    places.category,
                    COALESCE(categories.display_name, places.category) AS category_name,
                    COALESCE(categories.color, '#315f73') AS category_color,
                    COALESCE(categories.icon_name, 'place') AS category_icon,
                    places.latitude,
                    places.longitude,
                    places.description,
                    {OPENING_HOURS_SELECT_SQL},
                    {CLOSED_DATES_SELECT_SQL},
                    {ANNUAL_CLOSED_DATES_SELECT_SQL},
                    {RECURRING_CLOSED_DAYS_SELECT_SQL},
                    places.price_min,
                    places.price_max,
                    places.address,
                    places.website_url
                FROM public.places AS places
                LEFT JOIN public.place_categories AS categories
                    ON categories.value = places.category
                WHERE places.is_published = TRUE
                ORDER BY places.display_order, places.name
                LIMIT 500
                """
            )
            return cursor.fetchall()


def get_all_places():
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    places.id,
                    places.name,
                    COALESCE(categories.display_name, places.category) AS category_name,
                    places.address,
                    places.is_published
                FROM public.places AS places
                LEFT JOIN public.place_categories AS categories
                    ON categories.value = places.category
                ORDER BY places.created_at DESC, places.id DESC
                LIMIT 500
                """
            )
            return cursor.fetchall()


def get_place(place_id):
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    places.id,
                    places.name,
                    places.category,
                    places.latitude,
                    places.longitude,
                    places.description,
                    {OPENING_HOURS_SELECT_SQL},
                    {CLOSED_DATES_SELECT_SQL},
                    {ANNUAL_CLOSED_DATES_SELECT_SQL},
                    {RECURRING_CLOSED_DAYS_SELECT_SQL},
                    places.price_min,
                    places.price_max,
                    places.address,
                    places.website_url,
                    places.source_url,
                    places.last_verified_at,
                    places.is_published
                FROM public.places AS places
                WHERE places.id = %s
                """,
                (place_id,),
            )
            return cursor.fetchone()


def create_place(place):
    with connect_database() as connection:
        with connection.cursor() as cursor:
            return insert_place(cursor, place)


def create_places(places):
    with connect_database() as connection:
        with connection.cursor() as cursor:
            for place in places:
                insert_place(cursor, place)

    return len(places)


def update_place(place_id, place):
    values = {**place, "id": place_id}

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.places
                SET
                    name = %(name)s,
                    category = %(category)s,
                    latitude = %(latitude)s,
                    longitude = %(longitude)s,
                    description = %(description)s,
                    price_min = %(price_min)s,
                    price_max = %(price_max)s,
                    address = %(address)s,
                    website_url = %(website_url)s,
                    source_url = %(source_url)s,
                    last_verified_at = %(last_verified_at)s,
                    is_published = %(is_published)s
                WHERE id = %(id)s
                RETURNING id
                """,
                values,
            )
            updated = cursor.fetchone()
            if not updated:
                return None

            for table_name in (
                "place_opening_hours",
                "place_closed_dates",
                "place_annual_closures",
                "place_recurring_closures",
            ):
                cursor.execute(
                    f"DELETE FROM public.{table_name} WHERE place_id = %s",
                    (place_id,),
                )
            save_opening_hours(cursor, place_id, place["opening_hours"])
            save_closures(cursor, place_id, place)
            return updated["id"]


def delete_places(place_ids):
    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM public.places WHERE id = ANY(%s)",
                (place_ids,),
            )
            return cursor.rowcount
