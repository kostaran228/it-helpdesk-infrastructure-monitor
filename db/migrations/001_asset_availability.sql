DO $$
BEGIN
  CREATE TYPE assetavailability AS ENUM ('unknown', 'online', 'offline');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE assets
  ADD COLUMN IF NOT EXISTS availability assetavailability NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP NULL;
