import { describe, it, expect } from 'vitest';
import { ApiError } from '../src/api/client';

describe('VAAK API Client', () => {
  it('creates ApiError with proper status and code', () => {
    const err = new ApiError('Meeting not found', 404, 'NOT_FOUND');
    expect(err.message).toBe('Meeting not found');
    expect(err.status).toBe(404);
    expect(err.code).toBe('NOT_FOUND');
    expect(err.name).toBe('ApiError');
  });

  it('defaults to 500 status and INTERNAL_ERROR code', () => {
    const err = new ApiError('Unexpected error');
    expect(err.status).toBe(500);
    expect(err.code).toBe('INTERNAL_ERROR');
  });
});
