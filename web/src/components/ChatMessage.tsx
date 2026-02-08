'use client';

import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import TypewriterText from './TypewriterText';
import type { TutorEvent } from '@/lib/types';
import { EVENT_TYPES } from '@/lib/types';

interface ChatMessageProps {
  event: TutorEvent;
  animate?: boolean;
  onAnimationComplete?: () => void;
}

// Get styling based on event type
function getEventStyles(eventType: string): {
  containerClass: string;
  iconClass: string;
  icon: string;
} {
  switch (eventType) {
    case EVENT_TYPES.UNIT_OPENING:
      return {
        containerClass: 'bg-blue-50 border-blue-200',
        iconClass: 'text-blue-600',
        icon: '📚',
      };
    case EVENT_TYPES.POINT_OPENING:
      return {
        containerClass: 'bg-purple-50 border-purple-200',
        iconClass: 'text-purple-600',
        icon: '📌',
      };
    case EVENT_TYPES.POINT_EXPLANATION:
      return {
        containerClass: 'bg-white border-gray-200',
        iconClass: 'text-gray-600',
        icon: '💡',
      };
    case EVENT_TYPES.ASK_CHECK:
      return {
        containerClass: 'bg-yellow-50 border-yellow-200',
        iconClass: 'text-yellow-600',
        icon: '❓',
      };
    case EVENT_TYPES.FEEDBACK:
      return {
        containerClass: 'bg-green-50 border-green-200',
        iconClass: 'text-green-600',
        icon: '✅',
      };
    case EVENT_TYPES.ASK_CONFIRM_ADVANCE:
      return {
        containerClass: 'bg-indigo-50 border-indigo-200',
        iconClass: 'text-indigo-600',
        icon: '➡️',
      };
    case EVENT_TYPES.UNIT_NOTES:
      return {
        containerClass: 'bg-teal-50 border-teal-200',
        iconClass: 'text-teal-600',
        icon: '📝',
      };
    default:
      return {
        containerClass: 'bg-gray-50 border-gray-200',
        iconClass: 'text-gray-600',
        icon: '💬',
      };
  }
}

// Determine typing speed from event data or type
function getSpeed(event: TutorEvent): 'slow' | 'normal' | 'fast' {
  // Check if pace is specified in data
  if (event.data?.pace) {
    const pace = event.data.pace as string;
    if (pace === 'slow' || pace === 'normal' || pace === 'fast') {
      return pace;
    }
  }

  // Default: explanations are normal, questions are fast
  if (event.event_type === EVENT_TYPES.POINT_EXPLANATION) {
    return 'normal';
  }
  return 'fast';
}

export default function ChatMessage({
  event,
  animate = false,
  onAnimationComplete,
}: ChatMessageProps) {
  const [showFull, setShowFull] = useState(!animate);
  const styles = getEventStyles(event.event_type);
  const speed = getSpeed(event);

  // If animation is disabled or complete, show full content
  useEffect(() => {
    if (!animate) {
      setShowFull(true);
    }
  }, [animate]);

  const handleAnimationComplete = () => {
    setShowFull(true);
    onAnimationComplete?.();
  };

  return (
    <div
      className={`rounded-lg border p-4 mb-3 ${styles.containerClass}`}
      data-event-id={event.event_id}
      data-turn-id={event.turn_id}
      data-seq={event.seq}
    >
      {/* Header with icon and title */}
      {event.title && (
        <div className="flex items-center gap-2 mb-2">
          <span className={`text-lg ${styles.iconClass}`}>{styles.icon}</span>
          <h3 className="font-semibold text-gray-800">{event.title}</h3>
        </div>
      )}

      {/* Content */}
      <div className="prose prose-sm max-w-none text-gray-700">
        {showFull ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {event.markdown}
          </ReactMarkdown>
        ) : (
          <TypewriterText
            text={event.markdown}
            speed={speed}
            onComplete={handleAnimationComplete}
          />
        )}
      </div>

      {/* Event metadata (debug) */}
      <div className="mt-2 text-xs text-gray-400 flex gap-2">
        <span>Turn: {event.turn_id}</span>
        <span>Seq: {event.seq}</span>
        <span className="uppercase">{event.event_type}</span>
      </div>
    </div>
  );
}
