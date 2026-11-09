import React, { useState } from 'react';
import {
  VideoTrack,
  useTracks,
  useParticipants,
  isTrackReference,
} from '@livekit/components-react';
import { Track } from 'livekit-client';

/**
 * 20+ Participant Scale Video Grid:
 * - Large Active Speaker Stage (spotlighting activeSpeaker.holder).
 * - Paginated thumbnail strip (6 per page) so 20+ participants do not choke rendering.
 * - Participant list panel showing languages and real-time speaking status.
 */
export function VideoGrid({ activeSpeaker, participantsList = [] }) {
  const [thumbnailPage, setThumbnailPage] = useState(0);
  const [showRoster, setShowRoster] = useState(false);
  const THUMBNAILS_PER_PAGE = 6;

  const tracks = useTracks(
    [
      { source: Track.Source.Camera, withPlaceholder: true },
      { source: Track.Source.ScreenShare, withPlaceholder: false },
    ],
    { onlySubscribed: false }
  );

  const holderId = activeSpeaker?.holder;
  const overlapIds = activeSpeaker?.overlap || [];

  // Identify track for the main active speaker stage
  const mainTrack =
    tracks.find((t) => t.participant.identity === holderId) ||
    tracks.find((t) => !t.participant.isLocal) ||
    tracks[0];

  // Remaining tracks for thumbnail strip
  const otherTracks = tracks.filter((t) => t !== mainTrack);
  const totalPages = Math.max(1, Math.ceil(otherTracks.length / THUMBNAILS_PER_PAGE));
  const visibleThumbnails = otherTracks.slice(
    thumbnailPage * THUMBNAILS_PER_PAGE,
    (thumbnailPage + 1) * THUMBNAILS_PER_PAGE
  );

  return (
    <div className="video-grid-container" style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '8px' }}>
      {/* Top action row */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 4px' }}>
        <button
          type="button"
          onClick={() => setShowRoster(!showRoster)}
          style={{
            background: showRoster ? '#D3A376' : 'rgba(39, 44, 56, 0.8)',
            color: showRoster ? '#3E2522' : '#f3f4f6',
            border: '1px solid #374151',
            borderRadius: '6px',
            padding: '4px 10px',
            fontSize: '11px',
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          👥 Participants ({participantsList.length || tracks.length}) {showRoster ? '▲' : '▼'}
        </button>
      </div>

      {/* Participant Roster Drawer */}
      {showRoster && (
        <div style={{
          backgroundColor: '#1e222b',
          border: '1px solid #374151',
          borderRadius: '8px',
          padding: '8px 12px',
          maxHeight: '140px',
          overflowY: 'auto',
          fontSize: '12px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: '6px',
          zIndex: 10
        }}>
          {(participantsList.length > 0 ? participantsList : tracks.map(t => ({
            participant_id: t.participant.identity,
            name: t.participant.name || t.participant.identity,
            lang: 'en'
          }))).map((p) => {
            const isH = activeSpeaker?.holder === p.participant_id;
            const isO = activeSpeaker?.overlap?.includes(p.participant_id);
            return (
              <div
                key={p.participant_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  backgroundColor: isH ? 'rgba(211, 163, 118, 0.2)' : '#272c38',
                  border: isH ? '1px solid #D3A376' : '1px solid transparent',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                  <span style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: isH ? '#10b981' : isO ? '#f59e0b' : '#6b7280'
                  }} />
                  <span style={{ fontWeight: 600, color: '#f3f4f6', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.name}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ fontSize: '10px', textTransform: 'uppercase', padding: '1px 5px', borderRadius: '4px', backgroundColor: '#374151', color: '#D3A376' }}>
                    {p.lang || 'EN'}
                  </span>
                  {isH && <span style={{ fontSize: '10px', color: '#10b981', fontWeight: 700 }}>🎤 Holder</span>}
                  {isO && <span style={{ fontSize: '10px', color: '#f59e0b', fontWeight: 700 }}>💬 Overlap</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Main Large Active Speaker Stage */}
      <div style={{ flex: 1, minHeight: '260px', position: 'relative', borderRadius: '12px', overflow: 'hidden', border: '2px solid rgba(211, 163, 118, 0.4)' }}>
        {mainTrack ? (
          <SingleVideoTile
            trackRef={mainTrack}
            isHolder={activeSpeaker?.holder === mainTrack.participant.identity}
            isOverlap={activeSpeaker?.overlap?.includes(mainTrack.participant.identity)}
            isSpotlight
          />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9ca3af', backgroundColor: '#1e222b' }}>
            <span>Waiting for video tracks...</span>
          </div>
        )}
      </div>

      {/* 20+ Scale Paginated Thumbnail Strip */}
      {otherTracks.length > 0 && (
        <div style={{ height: '90px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          {totalPages > 1 && (
            <button
              type="button"
              onClick={() => setThumbnailPage((p) => Math.max(0, p - 1))}
              disabled={thumbnailPage === 0}
              style={{
                padding: '8px 10px',
                borderRadius: '6px',
                backgroundColor: '#272c38',
                color: '#fff',
                border: '1px solid #374151',
                cursor: thumbnailPage === 0 ? 'not-allowed' : 'pointer',
                opacity: thumbnailPage === 0 ? 0.4 : 1,
              }}
            >
              &lsaquo;
            </button>
          )}

          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: `repeat(${Math.min(visibleThumbnails.length, THUMBNAILS_PER_PAGE)}, 1fr)`, gap: '6px', height: '100%' }}>
            {visibleThumbnails.map((trackRef) => (
              <SingleVideoTile
                key={`${trackRef.participant.identity}-${trackRef.source}`}
                trackRef={trackRef}
                isHolder={activeSpeaker?.holder === trackRef.participant.identity}
                isOverlap={activeSpeaker?.overlap?.includes(trackRef.participant.identity)}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <button
              type="button"
              onClick={() => setThumbnailPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={thumbnailPage >= totalPages - 1}
              style={{
                padding: '8px 10px',
                borderRadius: '6px',
                backgroundColor: '#272c38',
                color: '#fff',
                border: '1px solid #374151',
                cursor: thumbnailPage >= totalPages - 1 ? 'not-allowed' : 'pointer',
                opacity: thumbnailPage >= totalPages - 1 ? 0.4 : 1,
              }}
            >
              &rsaquo;
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function SingleVideoTile({ trackRef, isHolder, isOverlap, isSpotlight = false }) {
  const p = trackRef.participant;
  const identity = p.identity;
  const name = p.name || identity;
  const hasVideo = isTrackReference(trackRef) && !trackRef.publication?.isMuted;

  let speakerClass = '';
  let badgeText = '';

  if (isHolder) {
    speakerClass = 'status-holder';
    badgeText = '🎤 Token Holder';
  } else if (isOverlap) {
    speakerClass = 'status-overlap';
    badgeText = '💬 Overlap';
  }

  return (
    <div
      className={`video-tile ${speakerClass}`}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        borderRadius: isSpotlight ? '0' : '8px',
        overflow: 'hidden',
        backgroundColor: '#121418',
        border: isHolder ? '2px solid #D3A376' : isOverlap ? '2px solid #f59e0b' : '1px solid #374151',
      }}
    >
      {hasVideo ? (
        <VideoTrack trackRef={trackRef} className="track-video" />
      ) : (
        <div className="avatar-placeholder" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <div className="avatar-circle" style={{
            width: isSpotlight ? '64px' : '32px',
            height: isSpotlight ? '64px' : '32px',
            fontSize: isSpotlight ? '1.5rem' : '0.8rem',
            borderRadius: '50%',
            backgroundColor: '#3E2522',
            color: '#FFF2DF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            border: '2px solid #D3A376'
          }}>
            {name.substring(0, 2).toUpperCase()}
          </div>
        </div>
      )}

      <div className="tile-overlay" style={{ position: 'absolute', bottom: '6px', left: '8px', right: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', pointerEvents: 'none' }}>
        <span className="tile-name" style={{ fontSize: isSpotlight ? '13px' : '10px', backgroundColor: 'rgba(0,0,0,0.6)', padding: '2px 6px', borderRadius: '4px', color: '#fff' }}>
          {name} {p.isLocal && '(You)'}
        </span>
        {badgeText && (
          <span className="speaker-badge" style={{
            fontSize: '10px',
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: '4px',
            backgroundColor: isHolder ? '#D3A376' : '#f59e0b',
            color: '#3E2522'
          }}>
            {badgeText}
          </span>
        )}
      </div>
    </div>
  );
}
