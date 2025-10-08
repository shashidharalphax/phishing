# App-wide config

# DB path (SQLite file)
DATABASE_URL = "sqlite:///./phishguard.db"

# Scheduler
SCHEDULER_TICK_SECONDS = 30
WORKER_CONCURRENCY = 1   # parallel scan workers

# CT watcher
ENABLE_CT_WATCHER = True
CT_BRAND_MATCH_RATIO = 85  # fuzzy match threshold to brand

# Limits
BULK_UPLOAD_MAX_ROWS = 1000
DEFAULT_SCAN_INTERVAL_MINUTES = 15
VERIFY_MIN_AGE_DAYS = 30