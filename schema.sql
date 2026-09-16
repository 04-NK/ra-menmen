CREATE TABLE IF NOT EXISTS public.places (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    description TEXT,
    price_level SMALLINT CHECK (price_level BETWEEN 1 AND 3),
    address TEXT,
    website_url TEXT,
    source_url TEXT,
    last_verified_at DATE,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS places_published_order_idx
    ON public.places (is_published, display_order);
