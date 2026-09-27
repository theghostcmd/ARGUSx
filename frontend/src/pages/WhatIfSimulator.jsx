import { useEffect, useState } from "react";
import { GitBranch, Minus, Plus, Loader2 } from "lucide-react";
import { Panel, Badge } from "../components/UI";
import { runSimulation } from "../api";

const actions = [
  ["isolate", "Isolate DEVICE-42",      "Contain the engineering workstation"],
  ["block",   "Block API-GW connection", "Stop east-west service access"],
  ["disable", "Disable USER-17",         "Remove privileged identity access"],
];

export default function WhatIfSimulator() {
  const [action, setAction] = useState("isolate");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    runSimulation(action)
      .then(setResult)
      .catch(() => setResult({ before: 0, after: 0, delta: 0, summary: "Backend unavailable" }))
      .finally(() => setLoading(false));
  }, [action]);

  if (loading || !result) {
    return (
      <div className="text-signal-grey flex items-center gap-2 p-6">
        <Loader2 className="animate-spin" size={16} /> Running simulation…
      </div>
    );
  }

  // ... keep the rest of the JSX exactly as it is ...
}