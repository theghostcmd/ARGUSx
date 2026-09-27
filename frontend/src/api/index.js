import axios from 'axios';

const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const client = axios.create({ baseURL: BASE, timeout: 15000 });

// ---------------- TELEMETRY ----------------
export const getTelemetry = async () => {
  const { data } = await client.get('/events');
  return data.events.map(e => ({
    event_id:   e.event_id,
    timestamp:  e.timestamp,
    event_type: e.event_type,
    user_id:    e.user_id,
    device_id:  e.device_id,
    severity:   deriveSeverity(e.event_type),
    source:     'backend',
  }));
};

// ---------------- INCIDENTS ----------------
export const getIncidents = async () => {
  const { data } = await client.get('/incidents');
  return data.incidents;
};

export const getIncidentById = async (id) => {
  const { data } = await client.get(`/incidents/${id}`);
  return data;
};

// ---------------- GRAPH ----------------
export const getGraph = async () => {
  const { data } = await client.get('/graph');
  return {
    nodes: data.nodes.map(n => ({
      id:     n.id,
      label:  n.id,
      type:   (n.type || 'entity').toLowerCase(),
      risk:   'medium',
      detail: `${n.type} entity`,
    })),
    edges: data.edges.map(e => [e.source, e.target]),
  };
};

// ---------------- WHAT-IF ----------------
export const runSimulation = async (actionId) => {
  const target =
    actionId === 'isolate' ? 'DEVICE-42' :
    actionId === 'block'   ? 'API-GW'    :
                             'USER-17';
  const { data } = await client.post('/simulation/what-if', {
    action: actionId,
    target,
  });
  return data;
};

// ---------------- helper ----------------
function deriveSeverity(t = '') {
  const t2 = t.toUpperCase();
  if (/(ANOMALY|LATERAL|PRIVILEGE|ESCALATION|DB_ACCESS|EXFIL)/.test(t2)) return 'CRITICAL';
  if (/(NEW_DEVICE|RESOURCE_ACCESS|OUTBOUND)/.test(t2))                return 'HIGH';
  if (/(LOGIN_FAILED|FAILED)/.test(t2))                                return 'MEDIUM';
  return 'LOW';
}