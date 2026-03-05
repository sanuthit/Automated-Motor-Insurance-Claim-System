import React from "react";

function badge(direction) {
  return direction === "increases_risk"
    ? <span className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-700">↑ increases</span>
    : <span className="text-xs px-2 py-0.5 rounded bg-green-50 text-green-700">↓ reduces</span>;
}

export default function InlineExplanation({ explanation, title = "Why?" }) {
  if (!explanation || !explanation.available) return null;

  const drivers = (explanation.top_drivers || []).slice(0, 4); // keep it compact near risk card
  if (!drivers.length) return null;

  return (
    <div className="mt-4 border-t pt-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-gray-800">{title}</h4>
        <span className="text-xs text-gray-500">{explanation.method || "SHAP"}</span>
      </div>

      <div className="space-y-2">
        {drivers.map((d, i) => (
          <div key={i} className="rounded-lg bg-gray-50 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">{d.feature}</div>
                <div className="text-xs text-gray-600 line-clamp-2">{d.reason}</div>
              </div>

              <div className="flex flex-col items-end shrink-0">
                {badge(d.direction)}
                <div className="text-xs text-gray-500 mt-1">
                  impact: {Number(d.shap_value).toFixed(3)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="text-[11px] text-gray-500 mt-2">
        Showing top {drivers.length} drivers. (Higher absolute impact = stronger influence)
      </div>
    </div>
  );
}