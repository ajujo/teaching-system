'use client';

import { useState, useEffect, useRef } from 'react';

interface TypewriterTextProps {
  text: string;
  speed?: 'slow' | 'normal' | 'fast';
  onComplete?: () => void;
  className?: string;
}

const SPEEDS = {
  slow: 50,    // 50ms per character
  normal: 20,  // 20ms per character
  fast: 5,     // 5ms per character
};

export default function TypewriterText({
  text,
  speed = 'normal',
  onComplete,
  className = '',
}: TypewriterTextProps) {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const indexRef = useRef(0);

  useEffect(() => {
    // Reset when text changes
    setDisplayedText('');
    setIsComplete(false);
    indexRef.current = 0;

    if (!text) {
      setIsComplete(true);
      onComplete?.();
      return;
    }

    const interval = setInterval(() => {
      if (indexRef.current < text.length) {
        setDisplayedText(text.slice(0, indexRef.current + 1));
        indexRef.current += 1;
      } else {
        clearInterval(interval);
        setIsComplete(true);
        onComplete?.();
      }
    }, SPEEDS[speed]);

    return () => clearInterval(interval);
  }, [text, speed, onComplete]);

  // Show cursor while typing
  return (
    <span className={className}>
      {displayedText}
      {!isComplete && <span className="animate-pulse">|</span>}
    </span>
  );
}
