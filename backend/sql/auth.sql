-- Uses the same PostgreSQL database/login as patient approval storage.
-- No extension, new database, or AWS administrator privilege is required.
CREATE TABLE IF NOT EXISTS twinverse_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('medical-student', 'faculty')),
    password_hash TEXT,
    google_sub TEXT UNIQUE,
    created_at BIGINT NOT NULL,
    CHECK (password_hash IS NOT NULL OR google_sub IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS twinverse_medical_student_profiles (
    user_id TEXT PRIMARY KEY REFERENCES twinverse_users(id) ON DELETE CASCADE,
    school TEXT NOT NULL DEFAULT '',
    study_year TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS twinverse_faculty_profiles (
    user_id TEXT PRIMARY KEY REFERENCES twinverse_users(id) ON DELETE CASCADE,
    institution TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS twinverse_auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES twinverse_users(id) ON DELETE CASCADE,
    created_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS twinverse_auth_sessions_user_idx ON twinverse_auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS twinverse_auth_sessions_expiry_idx ON twinverse_auth_sessions(expires_at);
CREATE TABLE IF NOT EXISTS twinverse_oauth_states (
    state_hash TEXT PRIMARY KEY,
    browser_hash TEXT NOT NULL,
    nonce TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    intent TEXT NOT NULL CHECK (intent IN ('login', 'signup', 'link')),
    role TEXT CHECK (role IN ('medical-student', 'faculty')),
    user_id TEXT REFERENCES twinverse_users(id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL,
    expires_at BIGINT NOT NULL
);

-- For a separate application login, the table owner may grant SELECT, INSERT,
-- UPDATE, DELETE on these tables. DELETE revokes sessions and consumes OAuth state.
