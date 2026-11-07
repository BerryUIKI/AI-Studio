import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CardMedia } from '../components/canvas/CardMedia';
import { downloadOriginalMedia, extensionForMime, mediaCardFields } from '../utils/media';
import { ImageCardData } from '../types/creative';

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('managed media cards', () => {
  it.each(['image/jpeg', 'image/webp', 'image/gif'])('renders %s as an image at an extensionless video-tagged URL', (mimeType) => {
    const data: ImageCardData = { imageUrl: '/api/v1/assets/fixture/content', videoUrl: '/api/v1/assets/fixture/content',
      mediaType: 'video', width: 8, height: 6, ...mediaCardFields({ mime_type: mimeType, is_animated: true }) };
    const markup = renderToStaticMarkup(<CardMedia data={data} url={data.imageUrl} onError={() => {}} />);
    expect(markup).toContain('<img');
    expect(markup).not.toContain('<video');
  });
  it('renders verified MP4 container metadata with video controls', () => {
    const data: ImageCardData = { imageUrl: '/api/v1/assets/fixture/content', width: 8, height: 6, mimeType: 'video/mp4' };
    expect(renderToStaticMarkup(<CardMedia data={data} url={data.imageUrl} onError={() => {}} />)).toContain('<video');
  });
  it.each([['image/jpeg', '.jpg'], ['image/webp', '.webp'], ['image/gif', '.gif'], ['video/mp4', '.mp4']])(
    'exports %s original bytes under the correct extension', async (mime, extension) => {
      const original = new Blob(['original-bytes'], { type: mime });
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, blob: async () => original }));
      const anchor = { href: '', download: '', click: vi.fn(), remove: vi.fn() };
      vi.stubGlobal('document', { createElement: () => anchor, body: { appendChild: vi.fn() } });
      const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fixture');
      await downloadOriginalMedia({ imageUrl: '/api/v1/assets/fixture/content', label: 'result.png', width: 8, height: 6 });
      expect(createUrl).toHaveBeenCalledWith(original);
      expect(anchor.download).toBe(`result${extension}`);
      expect(anchor.click).toHaveBeenCalledOnce();
      expect(extensionForMime(mime)).toBe(extension);
    },
  );
});
