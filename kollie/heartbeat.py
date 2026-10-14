import threading
import time

import structlog

logger = structlog.get_logger(__name__)

ALIVE_FILE = "/tmp/alive.txt"
UPDATE_INTERVAL = 60  # seconds


def update_alive_file():
    """
    Continuously update the timestamp of the /tmp/alive.txt file.
    """
    while True:
        try:
            with open(ALIVE_FILE, "w") as f:
                f.write(str(time.time()))
                logger.info(f"Updated {ALIVE_FILE}")
            time.sleep(UPDATE_INTERVAL)
        except Exception as e:
            logger.error(f"Failed to update {ALIVE_FILE}: {e}")
            break


def start_heartbeat():
    """
    Start the _update_alive_file function in a daemon thread.
    """
    threading.Thread(target=update_alive_file, daemon=True).start()
