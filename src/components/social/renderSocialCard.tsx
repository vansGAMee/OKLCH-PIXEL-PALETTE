import { ImageResponse } from 'next/og';

export const socialCardSize = {
  width: 1200,
  height: 630,
};

export function renderSocialCard(locale: 'en' | 'ru' = 'en') {
  const isRu = locale === 'ru';
  const subtitleText = isRu
    ? 'Палитры для пиксель-арта, игр и интерфейсов'
    : 'Perceptual palettes for pixel art, games and UI';

  const descText = isRu
    ? 'Палитры OKLCH из 2–9 цветов, шкала светлоты, пиксель-арт и защита sRGB.'
    : '2–9 color palettes with OKLCH lightness analysis & sRGB gamut protection.';

  const badgeText = isRu ? 'Защита гаммы sRGB' : 'sRGB Gamut Guarded';
  const tagText = isRu ? 'ДВИЖОК ЦВЕТОВОЙ ТЕОРИИ OKLCH' : 'OKLCH COLOR THEORY ENGINE';

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '60px',
          background: '#090909',
          color: '#f7f9fa',
          fontFamily: 'monospace',
          border: '12px solid #262626',
        }}
      >
        {/* Top Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: 'rgba(124, 58, 237, 0.2)',
                border: '2px solid rgba(139, 92, 246, 0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#a855f7',
                fontSize: '24px',
                fontWeight: 'bold',
              }}
            >
              P
            </div>
            <span style={{ fontSize: '28px', fontWeight: 'bold', letterSpacing: '1px', color: '#ffffff' }}>
              OKLCH PIXEL PALETTE
            </span>
          </div>

          <div
            style={{
              padding: '6px 16px',
              borderRadius: '8px',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#34d399',
              fontSize: '18px',
            }}
          >
            {badgeText}
          </div>
        </div>

        {/* Center Content */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div
            style={{
              fontSize: '48px',
              fontWeight: 900,
              lineHeight: 1.2,
              color: '#ffffff',
              maxWidth: '900px',
            }}
          >
            {subtitleText}
          </div>
          <div style={{ fontSize: '22px', color: '#9ca3af', maxWidth: '800px' }}>
            {descText}
          </div>
        </div>

        {/* Color Ramps Showcase */}
        <div style={{ display: 'flex', gap: '12px', width: '100%' }}>
          {['#1e1b4b', '#311b92', '#5b21b6', '#7c3aed', '#a855f7', '#c084fc', '#e879f9', '#f43f5e'].map(
            (hex, idx) => (
              <div
                key={idx}
                style={{
                  flex: 1,
                  height: '60px',
                  background: hex,
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                }}
              />
            )
          )}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#6b7280', fontSize: '18px' }}>
          <span>oklchpalette.ru</span>
          <span>{tagText}</span>
        </div>
      </div>
    ),
    {
      ...socialCardSize,
    }
  );
}
