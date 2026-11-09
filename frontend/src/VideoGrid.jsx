import React from 'react';
import {
  VideoTrack,
  useTracks,
  useParticipants,
  isTrackReference,
} from '@livekit/components-react';
import { Track } from 'livekit-client';

export function VideoGrid({ activeSpeaker }) {
  const participants = useParticipants();
  const tracks = useTracks(
    [
      { source: Track.Source.Camera, withPlaceholder: true },
      { source: Track.Source.ScreenShare, withPlaceholder: false },
    ],
    { onlySubscribed: false }
  );

  return (
    <div className="video-grid-container">
      <div className="video-grid">
        {tracks.map((trackRef) => {
          const p = trackRef.participant;
          const identity = p.identity;
          const name = p.name || identity;
          const isHolder = activeSpeaker?.holder === identity;
          const isOverlap = activeSpeaker?.overlap?.includes(identity);
          const hasVideo = isTrackReference(trackRef) && !trackRef.publication?.isMuted;

          let speakerStatusClass = '';
          let badgeText = '';

          if (isHolder) {
            speakerStatusClass = 'status-holder';
            badgeText = '🎤 Active Speaker';
          } else if (isOverlap) {
            speakerStatusClass = 'status-overlap';
            badgeText = '💬 Also Speaking';
          }

          return (
            <div
              key={`${identity}-${trackRef.source}`}
              className={`video-tile ${speakerStatusClass}`}
            >
              {hasVideo ? (
                <VideoTrack trackRef={trackRef} className="track-video" />
              ) : (
                <div className="avatar-placeholder">
                  <div className="avatar-circle">
                    {name.substring(0, 2).toUpperCase()}
                  </div>
                </div>
              )}

              <div className="tile-overlay">
                <span className="tile-name">
                  {name} {p.isLocal && '(You)'}
                </span>
                {badgeText && <span className="speaker-badge">{badgeText}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
