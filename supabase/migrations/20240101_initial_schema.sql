-- ==============================================================================
-- AI Video Synopsis & Meeting Transcription Platform - Supabase Schema
-- ==============================================================================

-- 1. Profiles Table (Synced automatically from auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger to create profile when auth.users signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, avatar_url)
    VALUES (
        new.id,
        new.email,
        COALESCE(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
        new.raw_user_meta_data->>'avatar_url'
    )
    ON CONFLICT (id) DO UPDATE
    SET full_name = EXCLUDED.full_name,
        avatar_url = EXCLUDED.avatar_url,
        updated_at = NOW();
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 2. Videos Table
CREATE TABLE IF NOT EXISTS public.videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    original_filename TEXT,
    file_type TEXT NOT NULL DEFAULT 'upload', -- 'upload' | 'youtube' | 'audio'
    storage_path TEXT,
    source_url TEXT,
    duration_seconds NUMERIC(10, 2),
    file_size_bytes BIGINT,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'extracting', 'transcribing', 'analyzing', 'completed', 'failed'
    progress_percent INT NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Transcripts Table
CREATE TABLE IF NOT EXISTS public.transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES public.videos(id) ON DELETE CASCADE,
    language TEXT DEFAULT 'en',
    raw_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Transcript Segments Table (Chronological Dialogue & Diarization)
CREATE TABLE IF NOT EXISTS public.transcript_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id UUID NOT NULL REFERENCES public.transcripts(id) ON DELETE CASCADE,
    start_time NUMERIC(10, 2) NOT NULL,
    end_time NUMERIC(10, 2) NOT NULL,
    speaker_label TEXT NOT NULL DEFAULT 'Speaker 1',
    display_name TEXT NOT NULL DEFAULT 'Speaker 1',
    text TEXT NOT NULL,
    is_unclear BOOLEAN DEFAULT FALSE,
    sequence_order INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Summaries Table (Executive Summary, Detailed Synopsis, Meeting Insights)
CREATE TABLE IF NOT EXISTS public.summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES public.videos(id) ON DELETE CASCADE,
    executive_summary TEXT NOT NULL,
    detailed_synopsis TEXT NOT NULL,
    key_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    conclusions JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_moments JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_meeting BOOLEAN DEFAULT FALSE,
    meeting_overview TEXT,
    decisions JSONB DEFAULT '[]'::jsonb,
    action_items JSONB DEFAULT '[]'::jsonb,
    open_questions JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for optimal lookup performance
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON public.videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON public.videos(status);
CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON public.transcripts(video_id);
CREATE INDEX IF NOT EXISTS idx_transcript_segments_transcript_id ON public.transcript_segments(transcript_id);
CREATE INDEX IF NOT EXISTS idx_transcript_segments_start_time ON public.transcript_segments(start_time);
CREATE INDEX IF NOT EXISTS idx_summaries_video_id ON public.summaries(video_id);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcript_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.summaries ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = id);

-- Videos Policies
CREATE POLICY "Users can view own videos"
    ON public.videos FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own videos"
    ON public.videos FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own videos"
    ON public.videos FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own videos"
    ON public.videos FOR DELETE
    USING (auth.uid() = user_id);

-- Transcripts Policies
CREATE POLICY "Users can view transcripts of their videos"
    ON public.transcripts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.videos
            WHERE videos.id = transcripts.video_id AND videos.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role can manage transcripts"
    ON public.transcripts FOR ALL
    USING (true);

-- Transcript Segments Policies
CREATE POLICY "Users can view segments of their videos"
    ON public.transcript_segments FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.transcripts
            JOIN public.videos ON videos.id = transcripts.video_id
            WHERE transcripts.id = transcript_segments.transcript_id
              AND videos.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update speaker display names in their segments"
    ON public.transcript_segments FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.transcripts
            JOIN public.videos ON videos.id = transcripts.video_id
            WHERE transcripts.id = transcript_segments.transcript_id
              AND videos.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role can manage segments"
    ON public.transcript_segments FOR ALL
    USING (true);

-- Summaries Policies
CREATE POLICY "Users can view summaries of their videos"
    ON public.summaries FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.videos
            WHERE videos.id = summaries.video_id AND videos.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role can manage summaries"
    ON public.summaries FOR ALL
    USING (true);

-- Storage bucket configuration (for Supabase Storage)
INSERT INTO storage.buckets (id, name, public)
VALUES ('media-vault', 'media-vault', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies: Users can upload and access only their own subfolder
CREATE POLICY "Users can upload media to own folder"
    ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'media-vault' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can view own media"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'media-vault' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can delete own media"
    ON storage.objects FOR DELETE
    USING (bucket_id = 'media-vault' AND auth.uid()::text = (storage.foldername(name))[1]);
