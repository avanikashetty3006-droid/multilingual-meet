import React, { useState } from "react";
import { JoinScreen } from "./JoinScreen";
import { VideoGrid } from "./VideoGrid";
import { SubtitlePanel } from "./SubtitlePanel";
import { useRoomSocket } from "./useRoomSocket";

export default function App() {
  const [session, setSession] = useState(null);

  if (!session) {
    return <JoinScreen onJoin={setSession} />;
  }

  return <ActiveCall session={session} onLeave={() => setSession(null)} />;
}

function ActiveCall({ session, onLeave }) {
  const {
    participants,
    activeSpeaker,
    currentMode,
    translations,
    overlapTranslations,
    setLanguage,
  } = useRoomSocket(session.room, session.participantId, session.name, session.lang);

  return (
    <div className="flex flex-col h-screen p-4 gap-4 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex justify-between items-center bg-slate-800 px-4 py-3 rounded-xl border border-slate-700">
        <div className="flex items-center gap-3">
          <span className="font-bold text-lg text-white">Multilingual Meet</span>
          <span className="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-300 font-mono">
            Room: {session.room}
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Hearing in:</span>
            <select
              value={session.lang}
              onChange={(e) => setLanguage(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white font-mono"
            >
              <option value="en">EN</option>
              <option value="hi">HI</option>
              <option value="kn">KN</option>
              <option value="ta">TA</option>
              <option value="te">TE</option>
              <option value="ml">ML</option>
              <option value="mr">MR</option>
            </select>
          </div>

          <button
            onClick={onLeave}
            className="bg-rose-600 hover:bg-rose-500 text-xs font-semibold px-3 py-1.5 rounded transition"
          >
            Leave
          </button>
        </div>
      </header>

      {/* Main Grid & Subtitle Panel */}
      <main className="flex-1 flex flex-col md:flex-row gap-4 overflow-hidden">
        <VideoGrid participants={participants} activeSpeaker={activeSpeaker} />
        <div className="w-full md:w-96 flex flex-col justify-end">
          <SubtitlePanel
            translations={translations}
            overlapTranslations={overlapTranslations}
            currentMode={currentMode}
          />
        </div>
      </main>
    </div>
  );
}
