import { useMemo, useState } from "react";
import { GitBranch, Minus, Plus } from "lucide-react";
import { Panel, Badge } from "../components/UI";

const actions = [
  [
    "isolate",
    "Isolate DEVICE-42",
    "Contain the engineering workstation",
  ],
  [
    "block",
    "Block API-GW connection",
    "Stop east-west service access",
  ],
  [
    "disable",
    "Disable USER-17",
    "Remove privileged identity access",
  ],
];

export default function WhatIfSimulator() {
  const [action, setAction] = useState("isolate");

  const result = useMemo(
    () =>
      ({
        isolate: {
          before: 94,
          after: 61,
          delta: -33,
          summary:
            "DEVICE-42 is removed from OT-NET adjacency. The reconstructed path breaks before the production database.",
        },
        block: {
          before: 94,
          after: 68,
          delta: -26,
          summary:
            "API-GW communication is blocked. Database reachability is removed, but the compromised identity remains active.",
        },
        disable: {
          before: 94,
          after: 48,
          delta: -46,
          summary:
            "USER-17 loses privileged access. Existing device exposure remains, but the current storyline cannot complete.",
        },
      })[action],
    [action]
  );

  return (
    <div className="space-y-4">
      <div>
        <div className="eyebrow">DIGITAL TWIN / RESPONSE VALIDATION</div>

        <h1 className="title">What-If Simulator</h1>
      </div>

      <div className="grid lg:grid-cols-[310px_1fr] gap-3">
        <Panel className="p-3">
          <div className="eyebrow px-1">RESPONSE ACTION</div>

          <div className="mt-3 space-y-2">
            {actions.map(([id, title, desc]) => (
              <button
                onClick={() => setAction(id)}
                key={id}
                className={`w-full text-left p-3 border ${
                  action === id
                    ? "border-signal-teal/40 bg-signal-teal/5"
                    : "border-base-700 bg-base-800"
                }`}
              >
                <div className="text-sm font-semibold">{title}</div>

                <div className="text-xs text-signal-grey mt-1">
                  {desc}
                </div>
              </button>
            ))}
          </div>
        </Panel>

        <div className="space-y-3">
          <Panel className="p-5">
            <div className="flex justify-between items-start">
              <div>
                <div className="eyebrow">SIMULATED OUTCOME</div>

                <h2 className="section-title">Risk before / after</h2>
              </div>

              <Badge tone="teal">NO LIVE CHANGES</Badge>
            </div>

            <div className="grid grid-cols-3 gap-3 mt-6">
              <div className="border border-base-700 p-4">
                <div className="eyebrow">BEFORE</div>

                <div className="text-4xl mono mt-2 text-signal-red">
                  {result.before}
                </div>
              </div>

              <div className="border border-base-700 p-4">
                <div className="eyebrow">DELTA</div>

                <div className="text-4xl mono mt-2 text-signal-teal">
                  {result.delta}
                </div>
              </div>

              <div className="border border-base-700 p-4">
                <div className="eyebrow">AFTER</div>

                <div className="text-4xl mono mt-2 text-signal-teal">
                  {result.after}
                </div>
              </div>
            </div>

            <div className="mt-5 border border-signal-teal/20 bg-signal-teal/5 p-4 text-sm leading-6">
              <GitBranch
                size={16}
                className="inline mr-2 text-signal-teal"
              />

              {result.summary}
            </div>
          </Panel>

          <Panel className="p-4">
            <div className="eyebrow">GRAPH DIFF</div>

            <div className="flex items-center gap-4 mt-5">
              <div className="node-pill">USER-17</div>

              <Plus size={14} />

              <div className="node-pill">DEVICE-42</div>

              <Minus size={14} className="text-signal-red" />

              <div className="node-pill muted">OT-NET</div>

              <Minus size={14} className="text-signal-red" />

              <div className="node-pill muted">PROD-DB-01</div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}