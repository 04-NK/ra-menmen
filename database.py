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
"""


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


# チーム用画面に登録済みの場所を表示する
def get_all_places():
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
                    address,
                    is_published,
                    created_at
                FROM public.places
                ORDER BY created_at DESC, id DESC
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
            cursor.execute(INSERT_PLACE_SQL, place)
            return cursor.fetchone()["id"]


# JSON内の場所を1回の処理でまとめて登録する
def create_places(places):
    with psycopg.connect(
        get_database_url(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            for place in places:
                cursor.execute(INSERT_PLACE_SQL, place)

    return len(places)


# 一覧で選択された場所をまとめて削除する
def delete_places(place_ids):
    with psycopg.connect(
        get_database_url(),
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM public.places WHERE id = ANY(%s)",
                (place_ids,),
            )
            return cursor.rowcount
