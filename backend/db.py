from contextlib import contextmanager
import psycopg2
from neo4j import GraphDatabase
from backend.config import (
    DATABASE_URL, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
)

_neo4j_driver = GraphDatabase.driver(
    NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)


def neo4j_driver():
    return _neo4j_driver


@contextmanager
def pg_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


def init_postgres_schema():
    with pg_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id     UUID PRIMARY KEY,
                timestamp    TIMESTAMPTZ NOT NULL,
                event_type   TEXT NOT NULL,
                user_id      TEXT NOT NULL,
                device_id    TEXT NOT NULL,
                ip_address   TEXT NOT NULL,
                service      TEXT NOT NULL,
                resource     TEXT NOT NULL
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp DESC);")
        conn.commit()
        cur.close()


def write_graph_event(event: dict):
    with neo4j_driver().session() as s:
        s.run("""
            MERGE (u:User {id: $user_id})
            MERGE (d:Device {id: $device_id})
            MERGE (ip:IPAddress {address: $ip_address})
            MERGE (s:Service {name: $service})
            MERGE (r:Resource {name: $resource})
            MERGE (u)-[:USES]->(d)
            MERGE (d)-[:HAS_IP]->(ip)
            MERGE (d)-[:ACCESSES]->(s)
            MERGE (s)-[:USES_RESOURCE]->(r)
        """, **{k: event[k] for k in
                ("user_id", "device_id", "ip_address", "service", "resource")})


def read_graph():
    with neo4j_driver().session() as s:
        result = s.run("""
            MATCH (a)-[r]->(b)
            RETURN
                labels(a) AS source_type,
                coalesce(a.id, a.name, a.address) AS source,
                type(r) AS relationship,
                labels(b) AS target_type,
                coalesce(b.id, b.name, b.address) AS target
        """)
        nodes, edges = {}, []
        for rec in result:
            src, tgt = rec["source"], rec["target"]
            nodes[src] = {"id": src, "type": rec["source_type"][0]}
            nodes[tgt] = {"id": tgt, "type": rec["target_type"][0]}
            edges.append({
                "source": src,
                "relationship": rec["relationship"],
                "target": tgt,
            })
        return {"nodes": list(nodes.values()), "edges": edges}