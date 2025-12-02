-- Delete all test bookings sent to jamie@teemail.io
-- Run this to clean up test data

\echo '============================================'
\echo 'DELETING TEST BOOKINGS'
\echo '============================================'

-- Show what will be deleted first
\echo 'Bookings that will be deleted:'
SELECT
    booking_id,
    guest_email,
    date,
    tee_time,
    golf_courses,
    status
FROM bookings
WHERE guest_email = 'jamie@teemail.io'
   OR booking_id LIKE 'TEST-%'
   OR booking_id LIKE 'EMAIL-TEST-%';

-- Count them
SELECT COUNT(*) as bookings_to_delete
FROM bookings
WHERE guest_email = 'jamie@teemail.io'
   OR booking_id LIKE 'TEST-%'
   OR booking_id LIKE 'EMAIL-TEST-%';

\echo ''
\echo 'Deleting...'

-- Delete the test bookings
DELETE FROM bookings
WHERE guest_email = 'jamie@teemail.io'
   OR booking_id LIKE 'TEST-%'
   OR booking_id LIKE 'EMAIL-TEST-%';

\echo ''
\echo '✅ Test bookings deleted!'
\echo ''
\echo 'Remaining bookings:'
SELECT COUNT(*) as remaining_bookings FROM bookings;
