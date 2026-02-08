// Types matching the FastAPI backend schemas

export interface Student {
  student_id: string;
  name: string;
  surname: string;
  email: string;
  tutor_persona_id: string;
  created_at: string;
  updated_at: string;
}

export interface StudentCreate {
  name: string;
  surname?: string;
  email?: string;
  tutor_persona_id?: string;
}

export interface TeachingPolicy {
  max_attempts_per_point: number;
  remediation_style: string;
  allow_advance_on_failure: boolean;
  default_after_failure: string;
  max_followups_per_point: number;
}

export interface Persona {
  id: string;
  name: string;
  short_title: string;
  background: string;
  default: boolean;
  teaching_policy: TeachingPolicy | null;
}

export interface Session {
  session_id: string;
  student_id: string;
  book_id: string;
  chapter_number: number;
  unit_number: number;
  created_at: string;
  status: string;
}

export interface SessionStart {
  student_id: string;
  book_id: string;
  chapter_number?: number;
  unit_number?: number;
}

export interface TutorEvent {
  event_id: string;
  event_type: string;
  turn_id: number;
  seq: number;
  title: string;
  markdown: string;
  data: Record<string, unknown>;
}

// Event types for styling
export const EVENT_TYPES = {
  UNIT_OPENING: 'UNIT_OPENING',
  POINT_OPENING: 'POINT_OPENING',
  POINT_EXPLANATION: 'POINT_EXPLANATION',
  ASK_CHECK: 'ASK_CHECK',
  FEEDBACK: 'FEEDBACK',
  ASK_CONFIRM_ADVANCE: 'ASK_CONFIRM_ADVANCE',
  UNIT_NOTES: 'UNIT_NOTES',
  ASK_UNIT_NEXT: 'ASK_UNIT_NEXT',
} as const;
