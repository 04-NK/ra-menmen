-- 場所登録で選べるカテゴリ
CREATE TABLE IF NOT EXISTS public.place_categories (
    value TEXT PRIMARY KEY CHECK (value ~ '^[a-z0-9_-]+$'),
    display_name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#315f73'
        CONSTRAINT place_categories_color_check
        CHECK (color ~ '^#[0-9a-fA-F]{6}$'),
    icon_name TEXT NOT NULL DEFAULT 'place'
        CONSTRAINT place_categories_icon_name_check
        CHECK (icon_name IN ('place', 'restaurant', 'cafe', 'shop', 'sightseeing', 'park', 'museum')),
    display_order INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.place_categories
    ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS color TEXT,
    ADD COLUMN IF NOT EXISTS icon_name TEXT;

UPDATE public.place_categories
SET color = CASE value
    WHEN 'restaurant' THEN '#a84436'
    WHEN 'cafe' THEN '#8a5d28'
    WHEN 'fast_food' THEN '#b35c24'
    WHEN 'shop' THEN '#356b61'
    WHEN 'tourism' THEN '#315f73'
    WHEN 'park' THEN '#3f7148'
    WHEN 'museum' THEN '#765789'
    ELSE '#5f6d72'
END
WHERE color IS NULL;

UPDATE public.place_categories
SET icon_name = CASE value
    WHEN 'restaurant' THEN 'restaurant'
    WHEN 'cafe' THEN 'cafe'
    WHEN 'fast_food' THEN 'restaurant'
    WHEN 'shop' THEN 'shop'
    WHEN 'tourism' THEN 'sightseeing'
    WHEN 'park' THEN 'park'
    WHEN 'museum' THEN 'museum'
    ELSE 'place'
END
WHERE icon_name IS NULL;

ALTER TABLE public.place_categories
    ALTER COLUMN color SET DEFAULT '#315f73',
    ALTER COLUMN color SET NOT NULL,
    ALTER COLUMN icon_name SET DEFAULT 'place',
    ALTER COLUMN icon_name SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'place_categories_color_check'
    ) THEN
        ALTER TABLE public.place_categories
            ADD CONSTRAINT place_categories_color_check
            CHECK (color ~ '^#[0-9a-fA-F]{6}$');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'place_categories_icon_name_check'
    ) THEN
        ALTER TABLE public.place_categories
            ADD CONSTRAINT place_categories_icon_name_check
            CHECK (icon_name IN ('place', 'restaurant', 'cafe', 'shop', 'sightseeing', 'park', 'museum'));
    END IF;
END
$$;

INSERT INTO public.place_categories (
    value,
    display_name,
    color,
    icon_name,
    display_order
)
VALUES
    ('restaurant', 'レストラン', '#a84436', 'restaurant', 10),
    ('cafe', 'カフェ', '#8a5d28', 'cafe', 20),
    ('fast_food', '軽食', '#b35c24', 'restaurant', 30),
    ('shop', 'お店', '#356b61', 'shop', 40),
    ('tourism', '観光地', '#315f73', 'sightseeing', 50),
    ('park', '公園', '#3f7148', 'park', 60),
    ('museum', '博物館・美術館', '#765789', 'museum', 70),
    ('other', 'その他', '#5f6d72', 'place', 80)
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
    period_index SMALLINT NOT NULL DEFAULT 0 CHECK (period_index BETWEEN 0 AND 9),
    opens_at TIME,
    closes_at TIME,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (place_id, day_of_week, period_index),
    CHECK (
        (is_closed = TRUE AND opens_at IS NULL AND closes_at IS NULL)
        OR
        (is_closed = FALSE AND opens_at IS NOT NULL AND closes_at IS NOT NULL)
    )
);

-- 既存データを残したまま、1つの曜日に複数の営業時間を保存できるようにする
ALTER TABLE public.place_opening_hours
    ADD COLUMN IF NOT EXISTS period_index SMALLINT NOT NULL DEFAULT 0;

ALTER TABLE public.place_opening_hours
    DROP CONSTRAINT IF EXISTS place_opening_hours_pkey;

ALTER TABLE public.place_opening_hours
    ADD CONSTRAINT place_opening_hours_pkey
    PRIMARY KEY (place_id, day_of_week, period_index);

-- 年を含む臨時休業日
CREATE TABLE IF NOT EXISTS public.place_closed_dates (
    place_id BIGINT NOT NULL REFERENCES public.places (id) ON DELETE CASCADE,
    closed_on DATE NOT NULL,
    PRIMARY KEY (place_id, closed_on)
);

-- 元日など、毎年同じ月日に休む設定
CREATE TABLE IF NOT EXISTS public.place_annual_closures (
    place_id BIGINT NOT NULL REFERENCES public.places (id) ON DELETE CASCADE,
    month SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    day SMALLINT NOT NULL CHECK (
        day BETWEEN 1 AND CASE
            WHEN month IN (4, 6, 9, 11) THEN 30
            WHEN month = 2 THEN 29
            ELSE 31
        END
    ),
    PRIMARY KEY (place_id, month, day)
);

-- 第2火曜日など、毎月繰り返す定休日
CREATE TABLE IF NOT EXISTS public.place_recurring_closures (
    place_id BIGINT NOT NULL REFERENCES public.places (id) ON DELETE CASCADE,
    week_of_month SMALLINT NOT NULL CHECK (week_of_month BETWEEN 1 AND 5),
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    PRIMARY KEY (place_id, week_of_month, day_of_week)
);

CREATE INDEX IF NOT EXISTS places_published_order_idx
    ON public.places (is_published, display_order);
