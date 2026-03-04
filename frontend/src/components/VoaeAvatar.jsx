import { useState, useRef, forwardRef, useImperativeHandle } from 'react';

// ── Definición de visemas de Amazon Polly ────────────────────────────────────
// Cada visema define la forma de los labios como paths SVG (coordenadas relativas
// al origen del grupo <g transform="translate(100, 142)"> del avatar).
const VISEMES = {
  sil: { path: 'M -18 0 Q -9 4 0 4 Q 9 4 18 0',          fill: '',   teeth: '',   tongue: '' },
  p:   { path: 'M -20 0 L 20 0',                          fill: '',   teeth: '',   tongue: '' },
  f:   { path: 'M -16 -2 Q 0 6 16 -2',
         fill:   'M -16 -2 Q 0 6 16 -2 L 16 2 Q 0 8 -16 2 Z',
         teeth:  'M -14 -2 L 14 -2 L 14 1 Q 0 3 -14 1 Z',
         tongue: '' },
  t:   { path: 'M -18 -3 Q 0 10 18 -3',
         fill:   'M -18 -3 Q 0 10 18 -3 L 16 4 Q 0 14 -16 4 Z',
         teeth:  'M -15 -3 L 15 -3 L 13 2 Q 0 4 -13 2 Z',
         tongue: 'M -8 4 Q 0 12 8 4 Q 4 8 0 9 Q -4 8 -8 4 Z' },
  s:   { path: 'M -20 -1 Q 0 5 20 -1',
         fill:   'M -20 -1 Q 0 5 20 -1 L 18 5 Q 0 9 -18 5 Z',
         teeth:  'M -17 -1 L 17 -1 L 15 3 Q 0 5 -15 3 Z',
         tongue: '' },
  S:   { path: 'M -14 -2 Q 0 12 14 -2',
         fill:   'M -14 -2 Q 0 12 14 -2 L 12 5 Q 0 16 -12 5 Z',
         teeth:  'M -11 -2 L 11 -2 L 9 4 Q 0 7 -9 4 Z',
         tongue: 'M -7 6 Q 0 14 7 6 Q 2 10 0 11 Q -2 10 -7 6 Z' },
  r:   { path: 'M -16 0 Q -6 8 0 8 Q 6 8 16 0',
         fill:   'M -16 0 Q -6 8 0 8 Q 6 8 16 0 L 14 6 Q 0 14 -14 6 Z',
         teeth:  '',
         tongue: '' },
  k:   { path: 'M -18 -2 Q 0 14 18 -2',
         fill:   'M -18 -2 Q 0 14 18 -2 L 16 5 Q 0 18 -16 5 Z',
         teeth:  'M -15 -2 L 15 -2 L 13 3 Q 0 6 -13 3 Z',
         tongue: 'M -10 8 Q 0 18 10 8 Q 4 13 0 14 Q -4 13 -10 8 Z' },
  i:   { path: 'M -22 0 Q -8 10 0 10 Q 8 10 22 0',
         fill:   'M -22 0 Q -8 10 0 10 Q 8 10 22 0 L 20 7 Q 0 16 -20 7 Z',
         teeth:  'M -19 0 L 19 0 L 17 5 Q 0 8 -17 5 Z',
         tongue: '' },
  e:   { path: 'M -20 -1 Q -6 12 0 12 Q 6 12 20 -1',
         fill:   'M -20 -1 Q -6 12 0 12 Q 6 12 20 -1 L 18 6 Q 0 18 -18 6 Z',
         teeth:  'M -17 -1 L 17 -1 L 15 5 Q 0 8 -15 5 Z',
         tongue: 'M -9 8 Q 0 16 9 8 Q 3 12 0 13 Q -3 12 -9 8 Z' },
  '@': { path: 'M -18 -2 Q 0 16 18 -2',
         fill:   'M -18 -2 Q 0 16 18 -2 L 16 6 Q 0 20 -16 6 Z',
         teeth:  'M -15 -2 L 15 -2 L 13 4 Q 0 7 -13 4 Z',
         tongue: 'M -10 9 Q 0 18 10 9 Q 4 14 0 15 Q -4 14 -10 9 Z' },
  a:   { path: 'M -16 -4 Q 0 22 16 -4',
         fill:   'M -16 -4 Q 0 22 16 -4 L 14 6 Q 0 26 -14 6 Z',
         teeth:  'M -13 -4 L 13 -4 L 11 3 Q 0 6 -11 3 Z',
         tongue: 'M -11 12 Q 0 24 11 12 Q 4 18 0 20 Q -4 18 -11 12 Z' },
  o:   { path: 'M -12 -4 Q -16 12 0 16 Q 16 12 12 -4',
         fill:   'M -12 -4 Q -16 12 0 16 Q 16 12 12 -4 Z',
         teeth:  '',
         tongue: 'M -7 8 Q 0 16 7 8 Q 2 13 0 14 Q -2 13 -7 8 Z' },
  u:   { path: 'M -8 -4 Q -12 10 0 14 Q 12 10 8 -4',
         fill:   'M -8 -4 Q -12 10 0 14 Q 12 10 8 -4 Z',
         teeth:  '',
         tongue: '' },
};

// Delays de animación para las 7 barras de audio
const BAR_DELAYS = [0, 0.1, 0.2, 0.3, 0.2, 0.1, 0];

const VoaeAvatar = forwardRef(function VoaeAvatar(_, ref) {
  const [visemeKey, setVisemeKey] = useState('sil');
  const [isSpeaking, setIsSpeaking] = useState(false);

  const queueRef      = useRef([]);       // [{audioBase64, visemes}]
  const isPlayingRef  = useRef(false);
  const isMutedRef    = useRef(false);
  const currentAudio  = useRef(null);
  const timersRef     = useRef([]);

  function clearTimers() {
    timersRef.current.forEach(t => clearTimeout(t));
    timersRef.current = [];
  }

  function scheduleVisemes(visemes) {
    clearTimers();
    visemes.forEach(({ time, value }) => {
      timersRef.current.push(setTimeout(() => setVisemeKey(value), time));
    });
  }

  function playNext() {
    if (isPlayingRef.current || queueRef.current.length === 0) return;

    const item = queueRef.current.shift();
    isPlayingRef.current = true;
    setIsSpeaking(true);

    const audio = new Audio(`data:audio/mp3;base64,${item.audioBase64}`);
    audio.muted = isMutedRef.current;
    currentAudio.current = audio;

    audio.addEventListener('play', () => scheduleVisemes(item.visemes));

    audio.addEventListener('ended', () => {
      isPlayingRef.current = false;
      currentAudio.current = null;
      clearTimers();
      if (queueRef.current.length === 0) {
        setIsSpeaking(false);
        setVisemeKey('sil');
      } else {
        playNext();
      }
    });

    audio.addEventListener('error', () => {
      isPlayingRef.current = false;
      currentAudio.current = null;
      clearTimers();
      playNext();
    });

    audio.play().catch(() => {
      isPlayingRef.current = false;
      playNext();
    });
  }

  useImperativeHandle(ref, () => ({
    speak(audioBase64, visemes = []) {
      queueRef.current.push({ audioBase64, visemes });
      playNext();
    },
    stop() {
      queueRef.current = [];
      clearTimers();
      if (currentAudio.current) {
        currentAudio.current.pause();
        currentAudio.current = null;
      }
      isPlayingRef.current = false;
      setIsSpeaking(false);
      setVisemeKey('sil');
    },
    mute() {
      isMutedRef.current = true;
      if (currentAudio.current) currentAudio.current.muted = true;
    },
    unmute() {
      isMutedRef.current = false;
      if (currentAudio.current) currentAudio.current.muted = false;
    },
  }));

  const v = VISEMES[visemeKey] || VISEMES.sil;

  return (
    <div className="voae-avatar-root">
      {/* CSS keyframes inyectados inline para evitar dependencia de archivo externo */}
      <style>{`
        @keyframes voae-pulse {
          0%, 100% { opacity: 0.6; transform: scale(1); }
          50%       { opacity: 1;   transform: scale(1.05); }
        }
        @keyframes voae-bar {
          0%, 100% { height: 5px;  opacity: 0.4; }
          50%       { height: 24px; opacity: 1;   }
        }
        .voae-avatar-root {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          padding: 32px 20px;
          height: 100%;
          justify-content: center;
        }
        .voae-glow {
          position: absolute;
          inset: -12px;
          border-radius: 50%;
          background: radial-gradient(circle, rgba(99,102,241,0.3) 0%, transparent 70%);
        }
        .voae-status {
          color: #94a3b8;
          font-size: 0.82rem;
          letter-spacing: 0.4px;
          margin: 0;
          font-family: 'Segoe UI', sans-serif;
        }
      `}</style>

      {/* Avatar SVG */}
      <div style={{ position: 'relative', width: 190, height: 190 }}>
        <div
          className="voae-glow"
          style={{
            animation: `voae-pulse ${isSpeaking ? '0.7s' : '2.5s'} ease-in-out infinite`,
          }}
        />
        <svg
          width="190"
          height="190"
          viewBox="0 0 200 200"
          xmlns="http://www.w3.org/2000/svg"
          style={{ filter: 'drop-shadow(0 4px 16px rgba(99,102,241,0.45))' }}
        >
          <defs>
            <radialGradient id="va-skin" cx="50%" cy="40%">
              <stop offset="0%" stopColor="#fcd9b6" />
              <stop offset="100%" stopColor="#f5a76c" />
            </radialGradient>
            <radialGradient id="va-bg" cx="50%" cy="50%">
              <stop offset="0%" stopColor="#312e81" />
              <stop offset="100%" stopColor="#1e1b4b" />
            </radialGradient>
          </defs>

          {/* Fondo */}
          <circle cx="100" cy="100" r="98" fill="url(#va-bg)" stroke="#6366f1" strokeWidth="2" />

          {/* Cuello */}
          <rect x="82" y="158" width="36" height="30" rx="8" fill="url(#va-skin)" />

          {/* Camisa */}
          <path d="M 40 200 Q 40 168 68 162 L 82 168 Q 100 178 118 168 L 132 162 Q 160 168 160 200 Z" fill="#4338ca" />
          <path d="M 100 172 L 94 200 M 100 172 L 106 200" stroke="#6366f1" strokeWidth="2" fill="none" />

          {/* Cara */}
          <ellipse cx="100" cy="102" rx="62" ry="68" fill="url(#va-skin)" />

          {/* Cabello */}
          <path d="M 38 88 Q 38 30 100 28 Q 162 30 162 88 Q 155 55 100 52 Q 45 55 38 88 Z" fill="#1c1917" />
          <path d="M 52 72 Q 60 58 74 62 Q 68 74 62 78 Z" fill="#1c1917" />
          <path d="M 148 72 Q 140 58 126 62 Q 132 74 138 78 Z" fill="#1c1917" />
          <path d="M 80 54 Q 90 44 110 46 Q 118 56 100 60 Q 84 56 80 54 Z" fill="#1c1917" />

          {/* Orejas */}
          <ellipse cx="38" cy="106" rx="9" ry="13" fill="#f5a76c" />
          <ellipse cx="162" cy="106" rx="9" ry="13" fill="#f5a76c" />
          <ellipse cx="38" cy="106" rx="5" ry="8" fill="#e8956d" />
          <ellipse cx="162" cy="106" rx="5" ry="8" fill="#e8956d" />

          {/* Cejas */}
          <path d="M 68 80 Q 80 74 90 78" stroke="#3d2b1f" strokeWidth="3.5" fill="none" strokeLinecap="round" />
          <path d="M 110 78 Q 120 74 132 80" stroke="#3d2b1f" strokeWidth="3.5" fill="none" strokeLinecap="round" />

          {/* Ojo izquierdo */}
          <ellipse cx="80" cy="96" rx="13" ry="12" fill="white" />
          <ellipse cx="80" cy="97" rx="8" ry="8" fill="#3b1f0e" />
          <ellipse cx="80" cy="97" rx="5" ry="5" fill="#1e0a03" />
          <circle cx="83" cy="94" r="2.5" fill="white" />

          {/* Ojo derecho */}
          <ellipse cx="120" cy="96" rx="13" ry="12" fill="white" />
          <ellipse cx="120" cy="97" rx="8" ry="8" fill="#3b1f0e" />
          <ellipse cx="120" cy="97" rx="5" ry="5" fill="#1e0a03" />
          <circle cx="123" cy="94" r="2.5" fill="white" />

          {/* Nariz */}
          <path d="M 97 104 Q 93 118 88 122 Q 100 126 112 122 Q 107 118 103 104" fill="#e8956d" opacity="0.6" />
          <ellipse cx="91" cy="122" rx="5" ry="3.5" fill="#d4845a" opacity="0.5" />
          <ellipse cx="109" cy="122" rx="5" ry="3.5" fill="#d4845a" opacity="0.5" />

          {/* Mejillas */}
          <ellipse cx="68" cy="118" rx="14" ry="8" fill="#f9a8d4" opacity="0.3" />
          <ellipse cx="132" cy="118" rx="14" ry="8" fill="#f9a8d4" opacity="0.3" />

          {/* Boca — controlada por visema */}
          <g transform="translate(100, 142)">
            {v.fill   && <path d={v.fill}   fill="#8b2635" />}
            {v.teeth  && <path d={v.teeth}  fill="white" />}
            {v.tongue && <path d={v.tongue} fill="#d4566a" />}
            <path
              d={v.path}
              fill="none"
              stroke="#c27451"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          </g>
        </svg>
      </div>

      {/* Barras de audio */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 28 }}>
        {BAR_DELAYS.map((delay, i) => (
          <div
            key={i}
            style={{
              width: 5,
              borderRadius: 3,
              background: '#6366f1',
              height: isSpeaking ? undefined : 5,
              opacity: isSpeaking ? undefined : 0.2,
              animation: isSpeaking
                ? `voae-bar 0.8s ease-in-out ${delay}s infinite`
                : 'none',
              transformOrigin: 'bottom',
            }}
          />
        ))}
      </div>

      {/* Estado */}
      <p className="voae-status">
        {isSpeaking ? 'Respondiendo...' : 'En espera...'}
      </p>
    </div>
  );
});

export default VoaeAvatar;
