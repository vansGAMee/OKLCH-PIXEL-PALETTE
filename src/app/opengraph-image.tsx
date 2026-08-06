import { renderSocialCard, socialCardSize } from '@/components/social/renderSocialCard';

export const alt = 'OKLCH Pixel Palette Generator';
export const size = socialCardSize;
export const contentType = 'image/png';

export default function OgImage() {
  return renderSocialCard('en');
}
