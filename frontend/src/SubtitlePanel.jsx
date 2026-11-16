import React from 'react';
import { latestPerTalker } from './captions';

/**
 * SubtitlePanel displays:
 * - Main lane captions (from token holder).
 * - Overlap lane captions ("Also speaking": one line per talker, max 2 talkers, Contract A4/B1).
 */
export function SubtitlePanel({ mainCaptions, overlapCaptions }) {
  const alsoSpeaking = latestPerTalker(overlapCaptions, 2);

  return (
    <div className="subtitles-container">
      {/* Main Speaker Lane */}
      <div className="subtitle-lane main-lane">
        <div className="lane-header">
          <span className="lane-badge main">Main Speaker</span>
        </div>
        <div className="captions-feed">
          {mainCaptions.length === 0 ? (
            <p className="caption-empty">Subtitles will appear here when participants speak...</p>
          ) : (
            mainCaptions.map((cap, idx) => (
              <div key={cap.chunk_id || idx} className="caption-entry">
                <div className="caption-meta">
                  <strong className="speaker-name">{cap.from_name || cap.from}</strong>
                  <span className="lang-tag">{cap.src_lang} &rarr; {cap.lang}</span>
                  <span className="mode-tag">{cap.mode}</span>
                </div>
                <p className="caption-text">{cap.text}</p>
                {cap.source_text && (
                  <p className="caption-source">"{cap.source_text}"</p>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Overlap Lane ("Also Speaking"): one line per distinct talker, max 2 (A4/B1) */}
      {alsoSpeaking.length > 0 && (
        <div className="subtitle-lane overlap-lane">
          <div className="lane-header">
            <span className="lane-badge overlap">Also Speaking</span>
          </div>
          <div className="captions-feed">
            {alsoSpeaking.map((cap, idx) => (
              <div key={cap.from || cap.chunk_id || idx} className="caption-entry overlap-entry">
                <div className="caption-meta">
                  <strong className="speaker-name">{cap.from_name || cap.from}</strong>
                  <span className="lang-tag">{cap.src_lang} &rarr; {cap.lang}</span>
                </div>
                <p className="caption-text">{cap.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
