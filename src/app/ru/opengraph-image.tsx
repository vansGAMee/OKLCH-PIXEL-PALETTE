import { renderSocialCard, socialCardSize } from '@/components/social/renderSocialCard';

export const alt = 'Генератор палитр OKLCH';
export const size = socialCardSize;
export const contentType = 'image/png';

export default function RuOgImage() {
  return renderSocialCard('ru');
}
