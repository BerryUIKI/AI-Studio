import { CreativeActionResult, ImageCardData } from '../types/creative';

export function mediaCardFields(media: Partial<CreativeActionResult>): Partial<ImageCardData> {
  return { mimeType: media.mime_type, extension: media.extension, isAnimated: media.is_animated, codec: media.codec };
}

export function isPlayableVideo(data: ImageCardData): boolean {
  if (data.mimeType) return data.mimeType.startsWith('video/');
  const url = data.videoUrl || data.imageUrl;
  if (/\.(webp|gif|png|jpe?g)(\?|#|$)/i.test(url)) return false;
  return data.mediaType === 'video' || Boolean(data.videoUrl);
}

export function extensionForMime(mime: string): string {
  const extensions: Record<string, string> = { 'image/png': '.png', 'image/jpeg': '.jpg',
    'image/webp': '.webp', 'image/gif': '.gif', 'video/mp4': '.mp4', 'video/webm': '.webm' };
  return extensions[mime.split(';')[0].trim()] || '.bin';
}

export async function downloadOriginalMedia(data: ImageCardData): Promise<void> {
  const url = data.videoUrl || data.imageUrl;
  if (!url) return;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const blob = await response.blob();
  const extension = extensionForMime(blob.type || data.mimeType || '');
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `${(data.label || 'berry_asset').replace(/\.[a-z0-9]+$/i, '')}${extension}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
