-- Migration: Add Resort Fees
-- Date: 2025-11-24
-- Description: Adds resort fee fields to bookings table and supports resort fees in tee time calculations

-- Add resort fee columns to bookings table
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS resort_fee_per_person DECIMAL(10,2) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS resort_fee_total DECIMAL(10,2) DEFAULT 0.00;

-- Add comments for documentation
COMMENT ON COLUMN bookings.resort_fee_per_person IS 'Resort fee charged per person per night';
COMMENT ON COLUMN bookings.resort_fee_total IS 'Total resort fees for the entire stay';

-- Note: Resort fees in selected_tee_times JSONB can be stored as:
-- {
--   "date": "...",
--   "time": "...",
--   "course_name": "...",
--   "players": N,
--   "price": X.XX,
--   "total_cost": Y.YY,
--   "resort_fee_per_person": Z.ZZ
-- }
