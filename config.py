from pathlib import Path

BASE_DIR = Path(__file__).parent

BRANDS = {
    "Mandi":    "mandi.basmati.morocco",
    "Fancy":    "fancy_morocco",
    "Elephant": "elephant_morocco",
    "Add-Me":   "addme.morocco",
}

TIMEZONE = "Africa/Casablanca"
SCRAPE_HOUR = 4
POSTS_PER_SCRAPE = 12
SLEEP_BETWEEN_POSTS = 8
SLEEP_BETWEEN_PROFILES = 75

DB_PATH = str(BASE_DIR / "data" / "akko.db")
SCHEMA_PATH = str(BASE_DIR / "schema.sql")
