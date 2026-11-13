import { describe, it, expect } from 'vitest';
import {
  generateMeetingId,
  parseMeetingId,
  normalizeMeetingId,
  isValidMeetingId,
} from '../src/utils/meetingId';

describe('Meeting ID utilities', () => {
  it('generates unguessable 10-char hyphenated IDs matching xxx-xxxx-xxx', () => {
    const id = generateMeetingId();
    expect(id).toMatch(/^[a-z0-9]{3}-[a-z0-9]{4}-[a-z0-9]{3}$/);
  });

  it('validates proper hyphenated IDs', () => {
    expect(isValidMeetingId('abc-defg-hij')).toBe(true);
    expect(isValidMeetingId('123-4567-890')).toBe(true);
    expect(isValidMeetingId('xyz-uvwx-rst')).toBe(true);
  });

  it('normalizes unhyphenated 10-character string to hyphenated format', () => {
    expect(normalizeMeetingId('abcdefghij')).toBe('abc-defg-hij');
  });

  it('parses full URL format with /m/ path', () => {
    const url = 'https://vaak.ai/m/abc-defg-hij';
    expect(parseMeetingId(url)).toBe('abc-defg-hij');
  });

  it('rejects invalid or malformed IDs', () => {
    expect(isValidMeetingId('')).toBe(false);
    expect(isValidMeetingId(null)).toBe(false);
    expect(isValidMeetingId('abc')).toBe(false);
    expect(isValidMeetingId('too-long-invalid-id-string-that-does-not-match')).toBe(false);
  });
});
