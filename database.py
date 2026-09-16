import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()


class DatabaseNotConfiguredError(RuntimeError):
    pass


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise DatabaseNotConfiguredError

    return database_url


# Neonから公開中のスポットを取得する
def get_published_places():
    with psycopg.connect(
        get_database_url(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    category,
                    latitude,
                    longitude,
                    description,
                    price_level,
                    address,
                    website_url
                FROM public.places
                WHERE is_published = TRUE
                ORDER BY display_order, name
                LIMIT 500
                """
            )
            return cursor.fetchall()


# チーム用画面からスポットを登録する
def create_place(place):
    with psycopg.connect(
        get_database_url(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.places (
                    name,
                    category,
                    latitude,
                    longitude,
                    description,
                    price_level,
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
                    %(price_level)s,
                    %(address)s,
                    %(website_url)s,
                    %(source_url)s,
                    %(last_verified_at)s,
                    %(is_published)s
                )
                RETURNING id
                """,
                place,
            )
            return cursor.fetchone()["id"]
