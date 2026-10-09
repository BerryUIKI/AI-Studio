import { ImageCardData } from '../../types/creative';
import { isPlayableVideo } from '../../utils/media';

export function CardMedia({ data, url, onError }: { data: ImageCardData; url: string; onError: () => void }) {
  return isPlayableVideo(data) ? (
    <video src={url} controls loop playsInline className="w-full h-auto object-contain max-h-[360px]" onError={onError} />
  ) : (
    <img src={url} alt={data.label || 'Generated creative asset'} className="w-full h-auto object-contain select-none" loading="lazy" onError={onError} />
  );
}
