import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import KnowledgeGraph from './pages/KnowledgeGraph';
import Incidents from './pages/Incidents';
import IncidentDetail from './pages/IncidentDetail';
import ThreatModel from './pages/ThreatModel';
import WhatIfSimulator from './pages/WhatIfSimulator';
import './index.css';

function App(){return <BrowserRouter><Routes><Route element={<Layout/>}><Route path="/" element={<Dashboard/>}/><Route path="/graph" element={<KnowledgeGraph/>}/><Route path="/incidents" element={<Incidents/>}/><Route path="/incidents/:id" element={<IncidentDetail/>}/><Route path="/threat-model" element={<ThreatModel/>}/><Route path="/simulator" element={<WhatIfSimulator/>}/></Route></Routes></BrowserRouter>}
createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
