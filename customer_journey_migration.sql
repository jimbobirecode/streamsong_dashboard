-- ============================================================================
-- CUSTOMER JOURNEY EMAIL TRACKING - DATABASE MIGRATION
-- ============================================================================
-- This migration adds email tracking columns to your bookings table
-- Run this ONCE before using the customer journey email system

-- Add email tracking columns
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS pre_arrival_email_sent_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS post_play_email_sent_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS guest_name VARCHAR(255);

-- Create index for faster queries (optional but recommended)
CREATE INDEX IF NOT EXISTS idx_bookings_pre_arrival_email
ON bookings(pre_arrival_email_sent_at);

CREATE INDEX IF NOT EXISTS idx_bookings_post_play_email
ON bookings(post_play_email_sent_at);

CREATE INDEX IF NOT EXISTS idx_bookings_date_status
ON bookings(date, status);

-- Display confirmation
\echo ''
\echo '✅ Customer Journey Email Tracking Migration Complete!'
\echo ''
\echo 'Added columns:'
\echo '  - pre_arrival_email_sent_at'
\echo '  - post_play_email_sent_at'
\echo '  - guest_name'
\echo ''
\echo 'Created indexes for performance optimization'
\echo ''
