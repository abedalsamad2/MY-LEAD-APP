import time
import random
from config import MIN_DELAY, MAX_DELAY, NODE_WAIT, URL_MIN_WAIT, URL_MAX_WAIT

def polite_delay():
    """Random delay between node requests to avoid rate limits."""
    delay = random.uniform(MIN_DELAY, MAX_DELAY)
    time.sleep(delay)

def node_wait():
    """Wait for JavaScript to finish rendering the page result."""
    time.sleep(NODE_WAIT)

def url_wait():
    """
    Anti-block wait between each URL.
    Random delay so the tool doesn't look like a bot.
    Logs the wait time so user sees it in the terminal.
    """
    delay = random.uniform(URL_MIN_WAIT, URL_MAX_WAIT)
    print(f"\n  [wait] Anti-block wait: {delay:.1f}s before next URL...\n")
    time.sleep(delay)

