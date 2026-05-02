import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  validateISBN13,
  validateISBN10,
  isbn10ToISBN13,
  normalizeToISBN13,
  extractISBNCandidates,
  detectOCRISBN,
} from './isbnDetect.js';

// Mock Tesseract.js at top level
vi.mock('tesseract.js', () => ({
  createWorker: vi.fn().mockResolvedValue({
    setParameters: vi.fn(),
    recognize: vi.fn().mockResolvedValue({ data: { text: 'ISBN: 9780141036144' } }),
    terminate: vi.fn(),
  }),
}));

describe('isbnDetect Utils', () => {
  describe('Math Helpers', () => {
    it('validates ISBN-13 correctly', () => {
      expect(validateISBN13('9780141036144')).toBe(true);
      expect(validateISBN13('9780141036145')).toBe(false);
      expect(validateISBN13('123')).toBe(false);
    });

    it('validates ISBN-10 correctly', () => {
      expect(validateISBN10('0316015849')).toBe(true);
      expect(validateISBN10('8090273416')).toBe(true);
      expect(validateISBN10('031601584X')).toBe(false);
      expect(validateISBN10('123')).toBe(false);
    });

    it('converts ISBN-10 to ISBN-13', () => {
      expect(isbn10ToISBN13('0316015849')).toBe('9780316015844');
      expect(isbn10ToISBN13('invalid')).toBe(null);
    });

    it('normalizes raw strings to ISBN-13', () => {
      expect(normalizeToISBN13('978-0-141-03614-4')).toBe('9780141036144');
      expect(normalizeToISBN13('0316015849')).toBe('9780316015844');
      expect(normalizeToISBN13('not an isbn')).toBe(null);
      expect(normalizeToISBN13('')).toBe(null);
    });

    it('extracts ISBN candidates from text', () => {
      const text = 'Here is an ISBN-13: 9780141036144 and an ISBN-10: 0316015849 and garbage.';
      const candidates = extractISBNCandidates(text);
      expect(candidates).toContain('9780141036144');
      expect(candidates).toContain('9780316015844');
      expect(candidates.length).toBe(2);
    });
  });

  describe('OCR Detection', () => {
    it('detects ISBN via OCR', async () => {
      // Mock canvas/document
      vi.stubGlobal('document', {
        createElement: vi.fn().mockReturnValue({
          getContext: vi.fn().mockReturnValue({
            drawImage: vi.fn(),
          }),
          width: 0,
          height: 0,
        }),
      });

      const result = await detectOCRISBN({ naturalWidth: 100, naturalHeight: 100 });
      expect(result).toEqual(['9780141036144']);
      vi.unstubAllGlobals();
    });
  });
});
