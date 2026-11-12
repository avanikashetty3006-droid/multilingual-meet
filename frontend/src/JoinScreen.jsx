import React, { useState } from "react";

export function JoinScreen({ onJoin }) {
  const [name, setName] = useState("");
  const [room, setRoom] = useState("room1");
  const [lang, setLang] = useState("en");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    const pid = `p-${Math.random().toString(36).substring(2, 7)}`;
    onJoin({ name, room, lang, participantId: pid });
  };

  return (
    <div className="flex items-center justify-center min-h-[80vh]">
      <form
        onSubmit={handleSubmit}
        className="bg-slate-800 p-8 rounded-2xl border border-slate-700 shadow-xl w-full max-w-md space-y-5"
      >
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white">Join Meeting</h2>
          <p className="text-xs text-slate-400 mt-1">
            Multilingual Video Conferencing System
          </p>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Your Name</label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
            placeholder="e.g. Asha"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Room ID</label>
          <input
            type="text"
            required
            value={room}
            onChange={(e) => setRoom(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Preferred Language</label>
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500"
          >
            <option value="en">English (en)</option>
            <option value="hi">Hindi (hi)</option>
            <option value="kn">Kannada (kn)</option>
            <option value="ta">Tamil (ta)</option>
            <option value="te">Telugu (te)</option>
            <option value="ml">Malayalam (ml)</option>
            <option value="mr">Marathi (mr)</option>
          </select>
        </div>

        <button
          type="submit"
          className="w-full bg-sky-600 hover:bg-sky-500 transition py-2.5 rounded-lg font-semibold text-sm shadow-md shadow-sky-600/30"
        >
          Join Call
        </button>
      </form>
    </div>
  );
}
