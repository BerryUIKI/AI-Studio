import { useUiText } from '../../i18n/useUiText';
import { ImageCardData } from '../../types/creative';
import { isPlayableVideo } from '../../utils/media';

export function CardMedia({ data, url, onError }: { data: ImageCardData; url: string; onError: () => void }) {
  const ui = useUiText();
  return isPlayableVideo(data) ? (
    <video src={url} controls loop playsInline className="w-full h-auto object-contain max-h-[360px]" onError={onError} />
  ) : (
    <img src={url} alt={data.label || ui("ui_generated_creative_asset")} className="w-full h-auto object-contain select-none" loading="lazy" onError={onError} />
  );
}
