import {telemetry} from '../data/mock/telemetry';import {incidents} from '../data/mock/incidents';import {graph} from '../data/mock/graph';
export const getTelemetry=async()=>telemetry;export const getIncidents=async()=>incidents;export const getIncidentById=async(id)=>incidents.find(x=>x.id===id);export const getGraph=async()=>graph;
