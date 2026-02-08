'use client';

import { useState, useEffect, useRef } from 'react';

interface TypewriterTextProps {
  text: string;
  speed?: 'slow' | 'normal' | 'fast';
  onComplete?: () => void;
  className?: string;
}

// Base delay por carácter (ms) - velocidad 2x
const BASE_SPEEDS: Record<NonNullable<TypewriterTextProps['speed']>, number> = {
  slow: 28,    // ~36 chars/s
  normal: 16,  // ~62 chars/s
  fast: 8,     // ~125 chars/s
};

// Pausas extra (ms) según signo - reducidas a la mitad
const PUNCTUATION_PAUSE: Array<{ re: RegExp; extra: number }> = [
  { re: /[\.\!\?]$/, extra: 130 },    // fin de frase
  { re: /[:,;]$/, extra: 60 },        // pausa corta
  { re: /\n$/, extra: 110 },          // salto de línea
  { re: /\s$/, extra: 0 },            // espacio
];

function getDelay(char: string, base: number) {
  // Un pelín de variación para que no sea “robot”
  const jitter = Math.floor(Math.random() * 12); // 0-11ms

  for (const rule of PUNCTUATION_PAUSE) {
    if (rule.re.test(char)) return base + rule.extra + jitter;
  }
  return base + jitter;
}

export default function TypewriterText({
  text,
  speed = 'normal',
  onComplete,
  className = '',
}: TypewriterTextProps) {
  const [displayedText, setDisplayedText] = useState('');
  const indexRef = useRef(0);
  const timeoutRef = useRef<number | null>(null);
  const completedRef = useRef(false);

  useEffect(() => {
    // Reset al cambiar texto
    setDisplayedText('');
    indexRef.current = 0;
    completedRef.current = false;

    if (!text) {
      onComplete?.();
      return;
    }

    const base = BASE_SPEEDS[speed];

    const tick = () => {
      if (indexRef.current >= text.length) {
        if (!completedRef.current) {
          completedRef.current = true;
          onComplete?.();
        }
        return;
      }

      indexRef.current += 1;
      const nextText = text.slice(0, indexRef.current);
      setDisplayedText(nextText);

      const lastChar = nextText[nextText.length - 1] ?? '';
      const delay = getDelay(lastChar, base);

      timeoutRef.current = window.setTimeout(tick, delay);
    };

    timeoutRef.current = window.setTimeout(tick, base);

    return () => {
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    };
  }, [text, speed, onComplete]);

  const isComplete = displayedText.length >= text.length;

  return (
    <span className={className}>
      {displayedText}
      {!isComplete && <span className="animate-pulse">|</span>}
    </span>
  );
}
