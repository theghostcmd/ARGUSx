import random
import requests
from datetime import datetime, timezone

EVENT_TYPES = [
    "LOGIN_SUCCESS", "LOGIN_FAILED", "AUTH_ANOMALY",
    "NEW_DEVICE", "NETWORK_ANOMALY", "RESOURCE_ACCESS",
]
USERS   = ["USER-17", "USER-21", "USER-35"]
DEVICES = ["DEVICE-42", "DEVICE-51", "DEVICE-63"]
IPS     = ["192.168.1.25", "192.168.1.30", "192.168.1.45"]
SERVICES = ["Authentication", "Network", "File Server", "Database"]
RESOURCES = ["Login Portal", "Internal Server", "Employee Files", "Database-02"]


def generate_event():
    return {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "event_type": random.choice(EVENT_TYPES),
        "user_id":    random.choice(USERS),
        "device_id":  random.choice(DEVICES),
        "ip_address": random.choice(IPS),
        "service":    random.choice(SERVICES),
        "resource":   random.choice(RESOURCES),
    }


def send_event(event):
    r = requests.post("http://127.0.0.1:8000/events", json=event, timeout=10)
    print(r.status_code, r.json())


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    for _ in range(n):
        send_event(generate_event())