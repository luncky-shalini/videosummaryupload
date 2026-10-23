export interface Video {
  id: string;
  user_id?: string;
  title: string;
  original_filename?: string;
  file_type: 'upload' | 'youtube' | 'audio';
  storage_path?: string;
  source_url?: string;
  duration_seconds?: number;
  file_size_bytes?: number;
  status: 'pending' | 'extracting' | 'transcribing' | 'analyzing' | 'completed' | 'failed';
  progress_percent: number;
  error_message?: string;
  created_at?: string;
}

export interface TranscriptSegment {
  id?: string;
  transcript_id?: string;
  start_time: number;
  end_time: number;
  speaker_label: string;
  display_name: string;
  text: string;
  is_unclear?: boolean;
  sequence_order: number;
}

export interface Transcript {
  id: string;
  video_id: string;
  language: string;
  raw_text: string;
  segments: TranscriptSegment[];
}

export interface KeyMoment {
  time: string;
  timestamp_seconds: number;
  title: string;
  description: string;
}

export interface ActionItem {
  item: string;
  owner: string;
  deadline: string;
}

export interface Summary {
  id?: string;
  video_id: string;
  executive_summary: string;
  detailed_synopsis: string;
  key_topics: string[];
  conclusions: string[];
  key_moments: KeyMoment[];
  is_meeting: boolean;
  meeting_overview?: string;
  decisions: string[];
  action_items: ActionItem[];
  open_questions: string[];
}

export interface VideoDetail {
  video: Video;
  transcript?: Transcript | null;
  summary?: Summary | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{
    timestamp_seconds: number;
    timecode: string;
    speaker: string;
    snippet: string;
  }>;
  created_at: string;
}
