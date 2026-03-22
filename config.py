import os

# NVIDIA AI (free)
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "your_nvidia_key_here")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"

# SpiderFoot local REST API
SPIDERFOOT_URL = "http://127.0.0.1:5001"

# Delays (seconds)
NODE_WAIT = 4
MIN_DELAY = 2
MAX_DELAY = 5
URL_MIN_WAIT = 5
URL_MAX_WAIT = 30

# Retry settings
MAX_RETRIES = 3
RETRY_WAIT = 5

# Paths
OUTPUT_FILE = "output/results.csv"
CACHE_DIR = "cache"
PROGRESS_FILE = "output/progress.json"

# Priority pages to scrape
PRIORITY_PATHS = [
    "/about",
    "/about-us",
    "/team",
    "/our-team",
    "/leadership",
    "/management",
    "/contact",
    "/contact-us",
    "/people",
    "/staff",
]

# Decision maker title priority
TITLE_PRIORITY = [
    "ceo",
    "chief executive",
    "founder",
    "co-founder",
    "owner",
    "president",
    "managing director",
    "general manager",
    "director",
    "head of",
    "vp",
    "manager",
]
