-- 場所登録で選べるカテゴリ
CREATE TABLE IF NOT EXISTS public.place_categories (
    value TEXT PRIMARY KEY CHECK (value ~ '^[a-z0-9_-]+$'),
    display_name TEXT NOT NULL UNIQUE,
    display_order INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.place_categories
    ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 100;

INSERT INTO public.place_categories (value, display_name, display_order)
VALUES
    ('restaurant', 'レストラン', 10),
    ('cafe', 'カフェ', 20),
    ('fast_food', '軽食', 30),
    ('shop', 'お店', 40),
    ('tourism', '観光地', 50),
    ('park', '公園', 60),
    ('museum', '博物館・美術館', 70),
    ('other', 'その他', 80)
ON CONFLICT (value) DO UPDATE
SET display_order = EXCLUDED.display_order;

CREATE TABLE IF NOT EXISTS public.places (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    description TEXT,
    price_min INTEGER CHECK (price_min >= 0),
    price_max INTEGER CHECK (price_max >= 0),
    price_level SMALLINT CHECK (price_level BETWEEN 1 AND 3),
    address TEXT,
    website_url TEXT,
    source_url TEXT,
    last_verified_at DATE,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 既存のテーブルにも新しい項目を追加する
ALTER TABLE public.places
    ADD COLUMN IF NOT EXISTS price_min INTEGER CHECK (price_min >= 0),
    ADD COLUMN IF NOT EXISTS price_max INTEGER CHECK (price_max >= 0);

-- 未登録の曜日と定休日を区別できるよう、営業時間は曜日ごとに保存する
CREATE TABLE IF NOT EXISTS public.place_opening_hours (
    place_id BIGINT NOT NULL REFERENCES public.places (id) ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    opens_at TIME,
    closes_at TIME,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (place_id, day_of_week),
    CHECK (
        (is_closed = TRUE AND opens_at IS NULL AND closes_at IS NULL)
        OR
        (is_closed = FALSE AND opens_at IS NOT NULL AND closes_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS places_published_order_idx
    ON public.places (is_published, display_order);
