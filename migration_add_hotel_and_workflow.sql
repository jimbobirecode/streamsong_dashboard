-- Migration: Add Hotel Information and Update Workflow States
-- Date: 2025-11-16
-- Description: Adds hotel fields and updates status workflow to: Inquiry → Requested → Confirmed → Booked

-- Add hotel-related columns to bookings table
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS hotel_checkin DATE,
ADD COLUMN IF NOT EXISTS hotel_checkout DATE,
ADD COLUMN IF NOT EXISTS hotel_nights INTEGER,
ADD COLUMN IF NOT EXISTS hotel_rooms INTEGER,
ADD COLUMN IF NOT EXISTS hotel_cost DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS lodging_intent TEXT,
ADD COLUMN IF NOT EXISTS golf_dates TEXT[], -- Array of golf dates
ADD COLUMN IF NOT EXISTS golf_courses TEXT, -- Courses requested/booked
ADD COLUMN IF NOT EXISTS selected_tee_times JSONB; -- Store selected tee times

-- Update existing status values to new workflow
-- Pending → Inquiry (initial bot response sent)
-- Keep Confirmed → Confirmed (tee time/hotel booked, payment info sent)
-- Add new states: Requested (customer replied), Booked (payment received)

UPDATE bookings SET status = 'Inquiry' WHERE status = 'Pending';

-- Add comments for documentation
COMMENT ON COLUMN bookings.hotel_checkin IS 'Hotel check-in date';
COMMENT ON COLUMN bookings.hotel_checkout IS 'Hotel check-out date';
COMMENT ON COLUMN bookings.hotel_nights IS 'Number of hotel nights';
COMMENT ON COLUMN bookings.hotel_rooms IS 'Number of hotel rooms needed';
COMMENT ON COLUMN bookings.hotel_cost IS 'Estimated hotel cost';
COMMENT ON COLUMN bookings.lodging_intent IS 'Lodging intent/confidence from email parsing';
COMMENT ON COLUMN bookings.golf_dates IS 'Array of golf play dates';
COMMENT ON COLUMN bookings.golf_courses IS 'Golf courses requested/booked';
COMMENT ON COLUMN bookings.selected_tee_times IS 'JSON of selected tee times with details';

-- Create index on status for faster filtering
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
CREATE INDEX IF NOT EXISTS idx_bookings_hotel_checkin ON bookings(hotel_checkin);

-- Workflow States Reference:
-- 1. Inquiry: Initial contact, email sent by bot (automatic)
-- 2. Requested: Customer replied with choice (updated from email/dashboard)
-- 3. Confirmed: Tee time/hotel booked, payment info sent (manual via dashboard)
-- 4. Booked: Payment received, fully complete (manual via dashboard)
