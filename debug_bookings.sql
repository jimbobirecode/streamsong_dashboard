-- Debug Script: Check what bookings exist and their data
-- Run with: psql $DATABASE_URL < debug_bookings.sql

\echo '============================================'
\echo 'CHECKING BOOKINGS FOR WELCOME EMAILS'
\echo '(3 days from today)'
\echo '============================================'

SELECT
    booking_id,
    guest_email,
    date,
    tee_time,
    players,
    golf_courses,
    status,
    pre_arrival_email_sent_at
FROM bookings
WHERE date = CURRENT_DATE + INTERVAL '3 days'
ORDER BY tee_time;

\echo ''
\echo '============================================'
\echo 'CHECKING BOOKINGS FOR THANK YOU EMAILS'
\echo '(2 days ago)'
\echo '============================================'

SELECT
    booking_id,
    guest_email,
    date,
    tee_time,
    players,
    golf_courses,
    status,
    post_play_email_sent_at
FROM bookings
WHERE date = CURRENT_DATE - INTERVAL '2 days'
ORDER BY guest_email;

\echo ''
\echo '============================================'
\echo 'ALL CONFIRMED BOOKINGS (SAMPLE)'
\echo '============================================'

SELECT
    booking_id,
    guest_email,
    date,
    tee_time,
    players,
    golf_courses,
    status,
    CASE
        WHEN date = CURRENT_DATE + INTERVAL '3 days' THEN '← WELCOME EMAIL'
        WHEN date = CURRENT_DATE - INTERVAL '2 days' THEN '← THANK YOU EMAIL'
        ELSE ''
    END as email_type
FROM bookings
WHERE status = 'Confirmed'
ORDER BY date
LIMIT 30;

\echo ''
\echo '============================================'
\echo 'COLUMN CHECK: Does golf_courses exist?'
\echo '============================================'

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'bookings'
AND column_name IN ('golf_courses', 'tee_time', 'pre_arrival_email_sent_at', 'post_play_email_sent_at', 'guest_name')
ORDER BY column_name;
