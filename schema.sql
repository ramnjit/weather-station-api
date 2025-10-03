CREATE TABLE stations (
    station_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    location_text VARCHAR(255),
    api_key_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE readings (
    reading_id SERIAL PRIMARY KEY,
    station_id UUID NOT NULL REFERENCES stations(station_id),
    temperature_celsius DECIMAL(5, 2) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);