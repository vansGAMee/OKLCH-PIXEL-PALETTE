import { describe, it, expect } from 'vitest';
import { GET } from '@/app/api/lospec/route';
import { NextRequest } from 'next/server';

describe('lospec API proxy', () => {
  it('rejects invalid or unsafe slugs (SSRF protection)', async () => {
    const maliciousSlugs = [
      '../../etc/passwd',
      'localhost:3000',
      '127.0.0.1',
      'http://attacker.com',
      'invalid slug with spaces',
      'toolong'.repeat(20),
    ];

    for (const slug of maliciousSlugs) {
      const req = new NextRequest(`http://localhost/api/lospec?slug=${encodeURIComponent(slug)}`);
      const res = await GET(req);
      expect(res.status).toBe(400);
      const json = await res.json();
      expect(json.error).toBeDefined();
    }
  });

  it('rejects empty slug', async () => {
    const req = new NextRequest('http://localhost/api/lospec');
    const res = await GET(req);
    expect(res.status).toBe(400);
  });
});
