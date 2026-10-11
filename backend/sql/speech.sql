CREATE TABLE IF NOT EXISTS public.twinverse_speech_clips (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    document JSONB NOT NULL,
    created_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    UNIQUE (encounter_id, turn_id)
);
CREATE INDEX IF NOT EXISTS twinverse_speech_student_idx ON public.twinverse_speech_clips(student_id, created_at);
