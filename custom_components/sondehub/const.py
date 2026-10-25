"""Constants for the SondeHub integration."""

DOMAIN = "sondehub"

API_BASE = "https://api.v2.sondehub.org"
USER_AGENT = "HomeAssistant-SondeHub/0.1.0"

CONF_FLIGHT_RADIUS = "flight_radius_km"
CONF_LANDING_RADIUS = "landing_radius_km"
CONF_WATCH_RADIUS = "watch_radius_km"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_FLIGHT_RADIUS = 100  # km: "a sonde is flying near me"
DEFAULT_LANDING_RADIUS = 30  # km: "a sonde is predicted to land near me"
DEFAULT_WATCH_RADIUS = 300  # km: candidates for which we fetch a prediction
DEFAULT_SCAN_INTERVAL = 90  # seconds

# Only consider sondes heard during the last N seconds.
LAST_SECONDS = 1800
# Landing predictions are refreshed at most every N seconds per sonde.
PREDICTION_TTL = 300
# A sonde is considered "descending" below this vertical speed (m/s).
DESCENT_THRESHOLD = -1.0
# Forget notified serials after this many seconds.
NOTIFIED_TTL = 3 * 24 * 3600

EVENT_SONDE_NEARBY = f"{DOMAIN}_sonde_nearby"
EVENT_LANDING_NEARBY = f"{DOMAIN}_landing_nearby"
