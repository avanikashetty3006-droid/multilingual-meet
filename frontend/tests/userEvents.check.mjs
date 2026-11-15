import assert from 'node:assert/strict';
import { addToast, backoffMs, parseUserEvent, pickActiveMeeting, toastFromInvite } from '../src/utils/userEvents.js';

assert.equal(parseUserEvent('pong'), null);
assert.equal(parseUserEvent('{bad'), null);
assert.equal(parseUserEvent('{"nope":1}'), null);
assert.deepEqual(parseUserEvent('{"type":"presence","user_id":"u","presence":"online"}'), { type: 'presence', user_id: 'u', presence: 'online' });

assert.deepEqual([0, 1, 2, 3, 10].map(backoffMs), [1000, 2000, 4000, 8000, 30000]);

const inv = { type: 'invite', meeting_id: 'abc-defg-hij', title: 'Standup', from_user: { id: 'u1', display_name: 'Alice' } };
const t = toastFromInvite(inv);
assert.equal(t.meetingId, 'abc-defg-hij');
assert.equal(t.text, 'Alice invited you to Standup');
assert.equal(toastFromInvite({ type: 'invite' }), null);
assert.equal(toastFromInvite({ type: 'presence' }), null);
assert.equal(toastFromInvite({ type: 'invite', meeting_id: 'abc-defg-hij' }).text, 'A friend invited you to a meeting');

let list = addToast([], t);
list = addToast(list, { ...t });                       // same invite again: replaced, not duplicated
assert.equal(list.length, 1);
for (const n of ['a', 'b', 'c', 'd']) list = addToast(list, { id: n, meetingId: n, text: n });
assert.equal(list.length, 3);
assert.deepEqual(list.map((x) => x.id), ['b', 'c', 'd']);

assert.equal(pickActiveMeeting([{ id: 'x', active: false }, { id: 'y', active: true }, { id: 'z', active: true }]).id, 'y');
assert.equal(pickActiveMeeting([{ id: 'x', active: false }]), null);
assert.equal(pickActiveMeeting(undefined), null);
console.log('userEvents.check: all passed');
