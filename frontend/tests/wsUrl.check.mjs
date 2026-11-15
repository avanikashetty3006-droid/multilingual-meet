import { wsUrl } from '../src/utils/wsUrl.js';
import assert from 'node:assert/strict';

assert.equal(wsUrl('/ws/room/abc-defg-hij?participant_id=p-1', '', { protocol: 'https:', host: 'meet.example.com' }),
  'wss://meet.example.com/ws/room/abc-defg-hij?participant_id=p-1');
assert.equal(wsUrl('ws/audio/r/p', '', { protocol: 'http:', host: 'localhost:5173' }), 'ws://localhost:5173/ws/audio/r/p');
assert.equal(wsUrl('/ws/user', 'https://api.example.com/', null), 'wss://api.example.com/ws/user');
assert.equal(wsUrl('/ws/user', 'http://10.0.0.5:8000', null), 'ws://10.0.0.5:8000/ws/user');
assert.throws(() => wsUrl('/ws/user', '', null));
console.log('wsUrl.check: all passed');
