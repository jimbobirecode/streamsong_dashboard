-- Migration: Add Customer Journey Email Tracking
-- Date: 2025-12-02
-- Description: Adds columns to track welcome and thank you email sending timestamps

-- Add email tracking columns to bookings table
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS pre_arrival_email_sent_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS post_play_email_sent_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS guest_name VARCHAR(255);

-- Add comments for documentation
COMMENT ON COLUMN bookings.pre_arrival_email_sent_at IS 'Timestamp when welcome email was sent (3 days before play)';
COMMENT ON COLUMN bookings.post_play_email_sent_at IS 'Timestamp when thank you email was sent (2 days after play)';
COMMENT ON COLUMN bookings.guest_name IS 'Guest name for personalized emails';

-- Create indexes for email tracking queries
CREATE INDEX IF NOT EXISTS idx_bookings_pre_arrival_email ON bookings(pre_arrival_email_sent_at);
CREATE INDEX IF NOT EXISTS idx_bookings_post_play_email ON bookings(post_play_email_sent_at);
CREATE INDEX IF NOT EXISTS idx_bookings_play_date_status ON bookings(date, status);

-- Email Tracking Reference:
-- pre_arrival_email_sent_at: Set when welcome email is sent 3 days before play date
-- post_play_email_sent_at: Set when thank you email is sent 2 days after play date
