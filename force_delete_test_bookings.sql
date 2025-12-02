-- FORCE DELETE all test bookings (no confirmation)
-- Run: psql $DATABASE_URL < force_delete_test_bookings.sql

BEGIN;

\echo 'Deleting bookings sent to jamie@teemail.io...'
DELETE FROM bookings WHERE guest_email = 'jamie@teemail.io';

\echo 'Deleting bookings with TEST- prefix...'
DELETE FROM bookings WHERE booking_id LIKE 'TEST-%';

\echo 'Deleting bookings with EMAIL-TEST- prefix...'
DELETE FROM bookings WHERE booking_id LIKE 'EMAIL-TEST-%';

\echo 'Deleting bookings with JAMIE in booking_id...'
DELETE FROM bookings WHERE booking_id ILIKE '%JAMIE%';

COMMIT;

\echo ''
\echo '✅ ALL TEST BOOKINGS DELETED'
\echo ''

SELECT
    'Total remaining bookings: ' || COUNT(*)::text as result
FROM bookings;
