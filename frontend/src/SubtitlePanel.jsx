import React from "react";

export function SubtitlePanel({ translations, overlapTranslations, currentMode }) {
  return (
    <div className="bg-slate-800/90 border border-slate-700 rounded-lg p-4 flex flex-col gap-3 shadow-lg">
      <div className="flex justify-between items-center border-b border-slate-700 pb-2">
        <h3 className="font-semibold text-sm text-slate-300">Live Captions & Translations</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded font-mono ${
            currentMode === "audio"
              ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700"
              : "bg-amber-900/60 text-amber-300 border border-amber-700"
          }`}
        >
          {currentMode === "audio" ? "● Audio Mode" : "○ Subtitle Mode (Network Fallback)"}
        </span>
      </div>

      {/* Main Speaker Lane */}
      <div className="space-y-2 min-h-[120px] max-h-[180px] overflow-y-auto">
        {translations.length === 0 ? (
          <p className="text-xs text-slate-500 italic">Waiting for speech...</p>
        ) : (
          translations.map((t, idx) => (
            <div key={idx} className="bg-slate-700/50 p-2 rounded text-sm">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold text-sky-400">{t.from_name}</span>
                <span className="text-[10px] bg-slate-600 px-1.5 py-0.2 rounded uppercase">
                  {t.src_lang} → {t.lang}
                </span>
              </div>
              <p className="text-white font-medium">{t.text}</p>
              {t.source_text && (
                <p className="text-xs text-slate-400 italic mt-0.5">"{t.source_text}"</p>
              )}
            </div>
          ))
        )}
      </div>

      {/* Overlap Lane */}
      {overlapTranslations.length > 0 && (
        <div className="border-t border-slate-700 pt-2">
          <span className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">
            Also Speaking (Overlap Lane)
          </span>
          <div className="space-y-1 mt-1">
            {overlapTranslations.map((ot, idx) => (
              <div key={idx} className="text-xs bg-amber-950/40 border border-amber-900/60 p-1.5 rounded">
                <span className="font-semibold text-amber-300">{ot.from_name}: </span>
                <span className="text-slate-200">{ot.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
