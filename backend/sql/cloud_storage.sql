-- Run once as the table owner, or use python3 -m backend.cloud_storage init-db.
-- No superuser privilege, extension, sequence, or database creation is needed.
CREATE TABLE IF NOT EXISTS public.twinverse_patient_versions (
    patient_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    profile JSONB NOT NULL,
    files JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (patient_id, version)
);

-- If a separate app login is used, the owner can grant:
-- GRANT CONNECT ON DATABASE twinverse TO twinverse_app;
-- GRANT USAGE ON SCHEMA public TO twinverse_app;
-- GRANT SELECT, INSERT, UPDATE ON public.twinverse_patient_versions TO twinverse_app;
