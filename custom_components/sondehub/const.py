"""Constants for the SondeHub integration."""

DOMAIN = "sondehub"

API_BASE = "https://api.v2.sondehub.org"
USER_AGENT = "HomeAssistant-SondeHub/0.2.0"

CONF_FLIGHT_RADIUS = "flight_radius_km"
CONF_LANDING_RADIUS = "landing_radius_km"
CONF_WATCH_RADIUS = "watch_radius_km"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PREDICTION_INTERVAL = "prediction_interval"

DEFAULT_FLIGHT_RADIUS = 100  # km: "a sonde is flying near me"
DEFAULT_LANDING_RADIUS = 30  # km: "a sonde is predicted to land near me"
DEFAULT_WATCH_RADIUS = 300  # km: candidates for which we fetch a prediction

# SondeHub asks clients not to poll its API regularly (it is rate limited and
# shared by the whole community), so the defaults are deliberately relaxed.
DEFAULT_SCAN_INTERVAL = 300  # seconds between /sondes requests
DEFAULT_PREDICTION_INTERVAL = 600  # seconds between /predictions requests
MIN_INTERVAL = 60
MAX_INTERVAL = 3600
INTERVAL_STEP = 30

# "Check now" presses closer together than this are merged into one request.
CHECK_NOW_COOLDOWN = 30  # seconds
# Back-off used when SondeHub answers 429 without a Retry-After header.
RATE_LIMIT_BACKOFF = 600  # seconds
# Max serials per /predictions request (keeps the URL short).
PREDICTION_BATCH_SIZE = 50

# Only consider sondes heard during the last N seconds.
LAST_SECONDS = 1800
# A sonde is considered "descending" below this vertical speed (m/s).
DESCENT_THRESHOLD = -1.0
# Forget notified serials after this many seconds.
NOTIFIED_TTL = 3 * 24 * 3600

EVENT_SONDE_NEARBY = f"{DOMAIN}_sonde_nearby"
EVENT_LANDING_NEARBY = f"{DOMAIN}_landing_nearby"
