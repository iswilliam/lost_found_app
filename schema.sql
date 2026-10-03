-- Lost and Found Item Reporting System
-- Database schema (matches Chapter 3 design)

DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS lost_items;
DROP TABLE IF EXISTS found_items;
DROP TABLE IF EXISTS matches;

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',  -- 'user' or 'admin'
    date_registered TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lost_items (
    lost_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    location_lost TEXT NOT NULL,
    date_lost DATE NOT NULL,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'unresolved',  -- unresolved, matched, closed
    date_reported TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE found_items (
    found_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    location_found TEXT NOT NULL,
    date_found DATE NOT NULL,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'unresolved',  -- unresolved, matched, closed
    date_reported TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lost_id INTEGER NOT NULL,
    found_id INTEGER NOT NULL,
    match_score REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, confirmed, rejected
    date_matched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lost_id) REFERENCES lost_items(lost_id),
    FOREIGN KEY (found_id) REFERENCES found_items(found_id)
);
