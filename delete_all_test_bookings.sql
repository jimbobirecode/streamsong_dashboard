-- Delete ALL test bookings - comprehensive cleanup
-- Run: psql $DATABASE_URL < delete_all_test_bookings.sql

\echo '============================================'
\echo 'SHOWING ALL CURRENT BOOKINGS'
\echo '============================================'

SELECT
    booking_id,
    guest_email,
    date,
    status,
    club
FROM bookings
ORDER BY date DESC;

\echo ''
\echo '============================================'
\echo 'BOOKINGS TO DELETE'
\echo '============================================'

-- Show exactly what will be deleted
SELECT
    booking_id,
    guest_email,
    date,
    status
FROM bookings
WHERE
    guest_email = 'jamie@teemail.io'
    OR booking_id LIKE 'TEST%'
    OR booking_id LIKE 'EMAIL-TEST%'
    OR booking_id LIKE '%JAMIE%';

-- Count
SELECT
    COUNT(*) as total_to_delete
FROM bookings
WHERE
    guest_email = 'jamie@teemail.io'
    OR booking_id LIKE 'TEST%'
    OR booking_id LIKE 'EMAIL-TEST%'
    OR booking_id LIKE '%JAMIE%';

\echo ''
\echo 'Press Ctrl+C to cancel, or press Enter to continue deleting...'
\prompt 'Continue? [yes/no]' confirm

\echo ''
\echo 'Deleting...'

-- Delete bookings
DELETE FROM bookings
WHERE
    guest_email = 'jamie@teemail.io'
    OR booking_id LIKE 'TEST%'
    OR booking_id LIKE 'EMAIL-TEST%'
    OR booking_id LIKE '%JAMIE%';

\echo ''
\echo '✅ DELETION COMPLETE'
\echo ''
\echo 'Remaining bookings:'
SELECT COUNT(*) as remaining_bookings FROM bookings;

\echo ''
\echo 'Remaining bookings by status:'
SELECT status, COUNT(*) as count
FROM bookings
GROUP BY status
ORDER BY count DESC;
