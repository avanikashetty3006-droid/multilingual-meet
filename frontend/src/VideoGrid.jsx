import React from "react";

export function VideoGrid({ participants, activeSpeaker }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 flex-1">
      {participants.map((p) => {
        const isHolder = activeSpeaker.holder === p.participant_id;
        const isOverlap = activeSpeaker.overlap?.includes(p.participant_id);

        return (
          <div
            key={p.participant_id}
            className={`relative rounded-xl overflow-hidden aspect-video bg-slate-800 flex items-center justify-center border-2 transition-all duration-300 ${
              isHolder
                ? "border-emerald-500 shadow-lg shadow-emerald-500/20"
                : isOverlap
                ? "border-amber-500 shadow-md shadow-amber-500/20"
                : "border-slate-700"
            }`}
          >
            <div className="w-16 h-16 rounded-full bg-slate-700 flex items-center justify-center text-xl font-bold text-slate-300 uppercase">
              {p.name.slice(0, 2)}
            </div>

            {/* Badges */}
            <div className="absolute top-2 left-2 flex gap-1">
              {isHolder && (
                <span className="bg-emerald-600 text-white text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase animate-pulse">
                  Active Speaker
                </span>
              )}
              {isOverlap && (
                <span className="bg-amber-600 text-white text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase">
                  Overlap
                </span>
              )}
            </div>

            <div className="absolute bottom-2 left-2 right-2 flex justify-between items-center text-xs bg-slate-900/80 px-2 py-1 rounded">
              <span className="font-medium text-white">{p.name}</span>
              <span className="uppercase text-[10px] text-sky-400 font-mono">
                {p.lang}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
