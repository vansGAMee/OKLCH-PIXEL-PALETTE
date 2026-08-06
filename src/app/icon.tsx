import { ImageResponse } from 'next/og';

export const size = {
  width: 32,
  height: 32,
};
export const contentType = 'image/png';

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#090909',
          borderRadius: '8px',
          border: '1px solid rgba(139, 92, 246, 0.4)',
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: '2px',
          }}
        >
          <div style={{ width: '6px', height: '14px', background: '#3b0764', borderRadius: '1px' }} />
          <div style={{ width: '6px', height: '14px', background: '#7c3aed', borderRadius: '1px' }} />
          <div style={{ width: '6px', height: '14px', background: '#a855f7', borderRadius: '1px' }} />
          <div style={{ width: '6px', height: '14px', background: '#f43f5e', borderRadius: '1px' }} />
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
