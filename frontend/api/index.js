import axios from "axios";

const BASE =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export const getTelemetry = async () => {
  const response = await axios.get(`${BASE}/events`);
  return response.data;
};

export const getIncidents = async () => {
  const response = await axios.get(`${BASE}/incidents`);
  return response.data;
};

export const getIncidentById = async (id) => {
  const response = await axios.get(`${BASE}/incidents/${id}`);
  return response.data;
};

export const getGraph = async () => {
  const response = await axios.get(`${BASE}/graph`);
  return response.data;
};

export const runSimulation = async (payload) => {
  const response = await axios.post(
    `${BASE}/simulation/what-if`,
    payload
  );

  return response.data;
};
