"""
ARGUS-X Backend — single FastAPI app that integrates:
  - PostgreSQL (events)
  - Neo4j (security graph)
  - cyber/cyber_module.py (Member 1)
  - ai_engine/ (Member 2)
Frontend talks ONLY to this service.
"""
import sys
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- make sibling packages importable ---------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import ai_bridge, cyber_bridge                          # noqa: E402
from backend.config import FRONTEND_URL                              # noqa: E402
from backend.db import (                                             # noqa: E402
    init_postgres_schema, pg_conn, write_graph_event, read_graph,
)
from backend.schemas import (                                        # noqa: E402
    EventIn, WhatIfRequest, WhatIfResponse,
)


# --------------------------------------------------------------------------
# Lifespan
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_postgres_schema()
    ai_bridge.init_ai_engine()          # load model + fit baseline
    print("AI engine status:", ai_bridge.ai_status())
    yield


app = FastAPI(title="ARGUS-X Backend", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------
@app.get("/")
def root():
    return {"project": "ARGUS-X", "status": "online"}


@app.get("/health")
def health():
    return {"status": "healthy", "ai": ai_bridge.ai_status()}


# --------------------------------------------------------------------------
# POST /events  — ingest + analyze
# --------------------------------------------------------------------------
@app.post("/events")
def create_event(event: EventIn):
    event_id = str(uuid.uuid4())

    backend_event = {
        "event_id":   event_id,
        "timestamp":  event.timestamp.isoformat(),
        "event_type": event.event_type,
        "user_id":    event.user_id,
        "device_id":  event.device_id,
        "ip_address": event.ip_address,
        "service":    event.service,
        "resource":   event.resource,
    }

    # 1) Postgres
    with pg_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO events
               (event_id, timestamp, event_type, user_id, device_id,
                ip_address, service, resource)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (event_id, event.timestamp, event.event_type, event.user_id,
             event.device_id, event.ip_address, event.service, event.resource),
        )
        conn.commit()
        cur.close()

    # 2) Neo4j
    try:
        write_graph_event(backend_event)
    except Exception as e:                                   # noqa: BLE001
        print("Neo4j write failed:", e)

    # 3) Cyber module
    cyber_result = cyber_bridge.analyze_event(backend_event)

    # 4) AI engine
    ai_result = ai_bridge.analyze_event(backend_event)

    return {
        "message": "Event received",
        "event": backend_event,
        "cyber": cyber_result,
        "ai": ai_result,
    }


# --------------------------------------------------------------------------
# GET /events
# --------------------------------------------------------------------------
@app.get("/events")
def get_events(limit: int = 200):
    with pg_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT event_id, timestamp, event_type, user_id, device_id,
                   ip_address, service, resource
            FROM events
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        cur.close()

    events = [{
        "event_id":   str(r[0]),
        "timestamp":  r[1].isoformat(),
        "event_type": r[2],
        "user_id":    r[3],
        "device_id":  r[4],
        "ip_address": r[5],
        "service":    r[6],
        "resource":   r[7],
    } for r in rows]

    return {"count": len(events), "events": events}


# --------------------------------------------------------------------------
# GET /incidents  — derived from AI batch analysis
# --------------------------------------------------------------------------
def _severity_from_risk(level: str) -> str:
    return {"critical": "CRITICAL", "high": "HIGH",
            "medium": "MEDIUM", "low": "LOW"}.get(level.lower(), "MEDIUM")


@app.get("/incidents")
def get_incidents(limit: int = 100):
    events = get_events(limit=limit)["events"]
    if not events:
        return {"count": 0, "incidents": []}

    batch = ai_bridge.analyze_batch(events)

    if "error" in batch:
        # Fallback: build incidents from cyber module only
        return _incidents_from_cyber()

    incidents_out = []
    for inc in batch.get("incidents", []):
        member_ids = inc["related_event_ids"]
        member_results = [e for e in batch["events"] if e["event_id"] in member_ids]
        if not member_results:
            continue

        risks = [m["risk"]["risk_score"] for m in member_results]
        avg_risk = sum(risks) / len(risks)
        risk_score_100 = int(round(avg_risk * 100))

        # Use the highest risk-level among members
        levels = [m["risk"]["risk_level"] for m in member_results]
        top_level = min(levels, key=lambda x: {"critical": 0, "high": 1,
                                                "medium": 2, "low": 3}.get(x, 9))

        # Pick a representative asset (most common resource)
        resources = [m["event"]["resource"] for m in member_results]
        asset = max(set(resources), key=resources.count)

        # Timeline: [time, label, event_id]
        timeline = [[t["timestamp"][11:19], t["event_type"], t["event_id"]]
                    for t in inc["timeline"]]

        # Title from first event's resource + user
        first = member_results[0]
        title = f"Correlated activity around {first['event']['user_id']} → {asset}"

        explanation = first["explanation"]["summary"]

        incidents_out.append({
            "id":             inc["incident_id"],
            "title":          title,
            "severity":       _severity_from_risk(top_level),
            "status":         "OPEN",
            "risk_score":     risk_score_100,
            "asset":          asset,
            "related_events": member_ids,
            "timeline":       timeline,
            "explanation":    explanation,
        })

    return {"count": len(incidents_out), "incidents": incidents_out}


def _incidents_from_cyber():
    cyber = cyber_bridge.get_cyber_module()
    out = []
    for inc in cyber.incident_engine.incidents:
        out.append({
            "id":             inc.incident_id,
            "title":          inc.title,
            "severity":       inc.severity,
            "status":         inc.status,
            "risk_score":     min(100, inc.risk_score * 6),
            "asset":          inc.asset_id,
            "related_events": [e.details.get("event_id", "") for e in inc.events],
            "timeline":       [
                [e.timestamp[11:19], e.event_type, e.details.get("event_id", "")]
                for e in inc.events
            ],
            "explanation":    inc.reason or "Correlated by ARGUS-X cyber pipeline.",
        })
    return {"count": len(out), "incidents": out}


# --------------------------------------------------------------------------
# GET /incidents/{id}
# --------------------------------------------------------------------------
@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    data = get_incidents()
    for inc in data["incidents"]:
        if inc["id"] == incident_id:
            return inc
    raise HTTPException(status_code=404, detail="Incident not found")


# --------------------------------------------------------------------------
# GET /graph
# --------------------------------------------------------------------------
@app.get("/graph")
def get_graph():
    try:
        return read_graph()
    except Exception as e:                                   # noqa: BLE001
        return {"nodes": [], "edges": [], "error": str(e)}


# --------------------------------------------------------------------------
# POST /simulation/what-if
# --------------------------------------------------------------------------
@app.post("/simulation/what-if", response_model=WhatIfResponse)
def what_if(req: WhatIfRequest):
    # current risk = max risk_score among active incidents
    incidents = get_incidents()["incidents"]
    before = max((i["risk_score"] for i in incidents), default=60)

    deltas = {"isolate": -33, "block": -26, "disable": -46}
    delta = deltas.get(req.action, -20)
    after = max(0, min(100, before + delta))

    summaries = {
        "isolate": f"{req.target} removed from OT-NET adjacency. Path breaks before production DB.",
        "block":   f"{req.target} blocked. Database reachability removed, identity still active.",
        "disable": f"{req.target} disabled. Privileged access revoked.",
    }
    return WhatIfResponse(
        before=before, after=after, delta=delta,
        summary=summaries.get(req.action, "Simulated response applied."),
    )