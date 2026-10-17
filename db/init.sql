-- =============================================================================
-- Celestial Classifier — database schema
-- Executed automatically by the postgres image on FIRST start only
-- (i.e. when the `pgdata` volume is empty).
-- =============================================================================

-- Lookup table of every class the AI is allowed to return.
CREATE TABLE IF NOT EXISTS categories (
    slug          TEXT PRIMARY KEY,
    label         TEXT    NOT NULL,
    description   TEXT    NOT NULL,
    is_celestial  BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order    INTEGER NOT NULL DEFAULT 0
);

INSERT INTO categories (slug, label, description, is_celestial, sort_order) VALUES
    ('black_hole',        'Black Hole',        'A region of spacetime with gravity so strong nothing escapes; often seen as a dark shadow ringed by a glowing accretion disk or relativistic jets.', TRUE, 1),
    ('galaxy',            'Galaxy',            'A gravitationally bound system of billions of stars, gas and dust — spiral, elliptical, lenticular or irregular in shape.', TRUE, 2),
    ('star',              'Star',              'A single luminous sphere of plasma (including our Sun), possibly showing diffraction spikes, flares or a corona.', TRUE, 3),
    ('planet',            'Planet',            'A large body orbiting a star — e.g. Jupiter, Saturn with its rings, Mars, Earth from space or an exoplanet rendering.', TRUE, 4),
    ('moon',              'Moon',              'A natural satellite orbiting a planet, such as Earth''s Moon, Europa or Titan.', TRUE, 5),
    ('nebula',            'Nebula',            'A glowing or dark interstellar cloud of gas and dust: emission, reflection, planetary or dark nebulae.', TRUE, 6),
    ('cosmic_dust',       'Cosmic / Star Dust','Diffuse interstellar dust lanes, dark clouds or dense star-dust fields without one dominant structure.', TRUE, 7),
    ('star_cluster',      'Star Cluster',      'A tightly packed group of stars — open clusters like the Pleiades or globular clusters like M13.', TRUE, 8),
    ('supernova_remnant', 'Supernova Remnant', 'The expanding, filamentary shell of material left after a stellar explosion, e.g. the Crab Nebula.', TRUE, 9),
    ('comet',             'Comet',             'An icy body with a bright coma and one or more tails pointing away from the Sun.', TRUE, 10),
    ('asteroid',          'Asteroid',          'A small rocky or metallic body, typically irregular and cratered, orbiting the Sun.', TRUE, 11),
    ('quasar',            'Quasar',            'An extremely luminous active galactic nucleus powered by a supermassive black hole.', TRUE, 12),
    ('other_celestial',   'Other Celestial',   'A real astronomical object or phenomenon that does not fit the other categories (aurora seen from orbit, pulsar, gravitational lens, etc.).', TRUE, 13),
    ('not_celestial',     'Not Celestial',     'The image does not show an astronomical object — e.g. animals, people, food, buildings or everyday items.', FALSE, 14)
ON CONFLICT (slug) DO NOTHING;

-- Every image the user uploads and the AI's verdict about it.
CREATE TABLE IF NOT EXISTS classifications (
    id               SERIAL PRIMARY KEY,
    original_name    TEXT         NOT NULL,
    mime_type        TEXT         NOT NULL,
    image_size       INTEGER      NOT NULL CHECK (image_size > 0),
    image_data       BYTEA        NOT NULL,
    category         TEXT         NOT NULL REFERENCES categories(slug),
    confidence       NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    object_name      TEXT,
    description      TEXT,
    visual_features  JSONB        NOT NULL DEFAULT '[]'::jsonb,
    fun_fact         TEXT,
    model_used       TEXT         NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_classifications_category   ON classifications (category);
CREATE INDEX IF NOT EXISTS idx_classifications_created_at ON classifications (created_at DESC);
