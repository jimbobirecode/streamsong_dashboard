# Customer Journey Email Marketing Logic

Standalone module for automated pre-arrival and post-play email campaigns for golf bookings.

## 📋 What It Does

- **Pre-Arrival Emails**: Sends welcome emails 3 days before play date
- **Post-Play Emails**: Sends thank you emails 2 days after play date
- **Smart Tee Time Extraction**: Pulls tee times from multiple sources (JSON, note field, etc.)
- **Email Tracking**: Prevents duplicate sends by tracking sent emails
- **Batch Processing**: Process multiple emails at once

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install sendgrid psycopg pandas
```

### 2. Run Database Migration

```bash
psql $DATABASE_URL < customer_journey_migration.sql
```

This adds tracking columns to your bookings table:
- `pre_arrival_email_sent_at`
- `post_play_email_sent_at`
- `guest_name`

### 3. Set Environment Variables

```bash
export SENDGRID_API_KEY="SG.xxxx"
export FROM_EMAIL="bookings@yourgolfclub.com"
export FROM_NAME="Your Golf Club"
export SENDGRID_TEMPLATE_PRE_ARRIVAL="d-xxxxx"
export SENDGRID_TEMPLATE_POST_PLAY="d-xxxxx"
export DATABASE_URL="postgresql://..."
```

### 4. Test It (Dry Run)

```bash
# See what emails would be sent without actually sending
python customer_journey_marketing_logic.py pre-arrival --dry-run
python customer_journey_marketing_logic.py post-play --dry-run
```

### 5. Send Emails

```bash
# Send pre-arrival emails
python customer_journey_marketing_logic.py pre-arrival

# Send post-play emails
python customer_journey_marketing_logic.py post-play

# Process both types at once
python customer_journey_marketing_logic.py both

# Filter by club (multi-club systems)
python customer_journey_marketing_logic.py both --club=streamsong
```

---

## 📊 Database Schema Requirements

Your `bookings` table must have these columns:

**Required:**
- `booking_id` (VARCHAR) - Unique booking identifier
- `guest_email` (VARCHAR) - Guest email address
- `date` (DATE) - Play date
- `status` (VARCHAR) - Booking status ('Confirmed', etc.)
- `players` (INTEGER) - Number of players
- `golf_courses` (VARCHAR) - Course name

**Optional (but recommended):**
- `tee_time` (VARCHAR) - Tee time (e.g., "10:35 AM")
- `selected_tee_times` (JSONB/TEXT) - JSON with tee time data
- `note` (TEXT) - Email content that may contain tee time
- `guest_name` (VARCHAR) - Guest name
- `club` (VARCHAR) - Club name (for multi-club systems)
- `total` (DECIMAL) - Booking total
- `hotel_required` (BOOLEAN) - Hotel required flag
- `hotel_checkin` (DATE) - Hotel check-in date
- `hotel_checkout` (DATE) - Hotel check-out date

**Tracking (added by migration):**
- `pre_arrival_email_sent_at` (TIMESTAMP) - When pre-arrival email was sent
- `post_play_email_sent_at` (TIMESTAMP) - When post-play email was sent

---

## 🔧 Integration into Your Codebase

### Option 1: Use as Standalone Script

Just run the Python script directly (see Quick Start above).

### Option 2: Import as Module

```python
from customer_journey_marketing_logic import (
    get_upcoming_bookings,
    get_recent_bookings,
    send_pre_arrival_email,
    send_post_play_email,
    process_pre_arrival_emails,
    process_post_play_emails,
    EmailConfig
)

# Configure
EmailConfig.DATABASE_URL = "postgresql://..."
EmailConfig.SENDGRID_API_KEY = "SG.xxxx"
EmailConfig.TEMPLATE_PRE_ARRIVAL = "d-xxxxx"
EmailConfig.TEMPLATE_POST_PLAY = "d-xxxxx"

# Get bookings that need emails
upcoming = get_upcoming_bookings(club_filter='streamsong')
recent = get_recent_bookings(club_filter='streamsong')

# Send individual email
for booking in upcoming:
    success, message = send_pre_arrival_email(booking)
    print(f"{booking['booking_id']}: {message}")

# Or process in batch
sent, failed, results = process_pre_arrival_emails(club_filter='streamsong')
print(f"Sent: {sent}, Failed: {failed}")
```

### Option 3: Schedule with Cron

Run daily to automatically send emails:

```bash
# Add to crontab (runs at 9 AM daily)
0 9 * * * cd /path/to/app && /usr/bin/python3 customer_journey_marketing_logic.py both --club=streamsong
```

### Option 4: Integrate with Task Queue (Celery, etc.)

```python
from celery import Celery
from customer_journey_marketing_logic import process_pre_arrival_emails, process_post_play_emails

app = Celery('tasks')

@app.task
def send_pre_arrival_emails_task():
    sent, failed, results = process_pre_arrival_emails(club_filter='streamsong')
    return {'sent': sent, 'failed': failed}

@app.task
def send_post_play_emails_task():
    sent, failed, results = process_post_play_emails(club_filter='streamsong')
    return {'sent': sent, 'failed': failed}

# Schedule daily
from celery.schedules import crontab

app.conf.beat_schedule = {
    'send-pre-arrival-emails': {
        'task': 'tasks.send_pre_arrival_emails_task',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
    'send-post-play-emails': {
        'task': 'tasks.send_post_play_emails_task',
        'schedule': crontab(hour=10, minute=0),  # 10 AM daily
    },
}
```

---

## 🎨 SendGrid Template Variables

Your SendGrid templates should use these variables:

### Required Variables
```handlebars
{{guest_name}}           - Guest name (from guest_name or email)
{{booking_date}}         - Play date (formatted: "Thursday, June 11, 2026")
{{course_name}}          - Golf course name
{{tee_time}}             - Tee time (e.g., "10:35 AM" or "TBD")
{{player_count}}         - Number of players
{{booking_reference}}    - Booking ID
{{current_year}}         - Current year (for footer)
{{total}}                - Booking total (formatted: "$340.00")
```

### Example Template HTML
```html
<h1>Welcome {{guest_name}}!</h1>

<p>Your booking is confirmed for:</p>

<table>
  <tr>
    <td><strong>Date:</strong></td>
    <td>{{booking_date}}</td>
  </tr>
  <tr>
    <td><strong>Course:</strong></td>
    <td>{{course_name}}</td>
  </tr>
  <tr>
    <td><strong>Tee Time:</strong></td>
    <td>{{tee_time}}</td>
  </tr>
  <tr>
    <td><strong>Players:</strong></td>
    <td>{{player_count}}</td>
  </tr>
  <tr>
    <td><strong>Booking Ref:</strong></td>
    <td>{{booking_reference}}</td>
  </tr>
  <tr>
    <td><strong>Total:</strong></td>
    <td>{{total}}</td>
  </tr>
</table>

<p>We look forward to seeing you!</p>

<footer>© {{current_year}} Streamsong Golf Resort</footer>
```

---

## 🕐 Tee Time Extraction Logic

The system is smart about finding tee times from multiple sources:

1. **Direct `tee_time` column** - If populated, use it
2. **JSON in `selected_tee_times`** - Parse `{"time": "10:35 AM", ...}`
3. **Go map format** - Extract from `map[time:10:35 AM ...]`
4. **Note field regex** - Find patterns like "Time: 10:35 AM"
5. **Fallback to "TBD"** - If none of the above work

This handles various booking system formats automatically.

---

## ⏰ Customizing Timing

Change when emails are sent by modifying `EmailConfig`:

```python
from customer_journey_marketing_logic import EmailConfig

# Send welcome emails 5 days before (instead of 3)
EmailConfig.PRE_ARRIVAL_DAYS = 5

# Send thank you emails 1 day after (instead of 2)
EmailConfig.POST_PLAY_DAYS = 1

# Then process emails
process_pre_arrival_emails()
```

---

## 🔍 Monitoring & Debugging

### Check Sent Emails
```sql
-- View all sent pre-arrival emails
SELECT booking_id, guest_email, date, pre_arrival_email_sent_at
FROM bookings
WHERE pre_arrival_email_sent_at IS NOT NULL
ORDER BY pre_arrival_email_sent_at DESC
LIMIT 50;

-- View all sent post-play emails
SELECT booking_id, guest_email, date, post_play_email_sent_at
FROM bookings
WHERE post_play_email_sent_at IS NOT NULL
ORDER BY post_play_email_sent_at DESC
LIMIT 50;
```

### Check Pending Emails
```sql
-- Bookings that need pre-arrival emails (3 days from now)
SELECT booking_id, guest_email, date, tee_time
FROM bookings
WHERE status = 'Confirmed'
AND date = CURRENT_DATE + INTERVAL '3 days'
AND pre_arrival_email_sent_at IS NULL;

-- Bookings that need post-play emails (2 days ago)
SELECT booking_id, guest_email, date, tee_time
FROM bookings
WHERE status = 'Confirmed'
AND date = CURRENT_DATE - INTERVAL '2 days'
AND post_play_email_sent_at IS NULL;
```

### Reset Email Tracking (Testing)
```sql
-- Reset pre-arrival tracking for a specific booking
UPDATE bookings
SET pre_arrival_email_sent_at = NULL
WHERE booking_id = 'SSG-20251202-V4FK';

-- Reset all tracking for testing
UPDATE bookings
SET pre_arrival_email_sent_at = NULL,
    post_play_email_sent_at = NULL
WHERE club = 'streamsong';
```

---

## 📈 Analytics Queries

### Email Performance
```sql
-- 30-day email stats
SELECT
    COUNT(*) as total_bookings,
    COUNT(pre_arrival_email_sent_at) as pre_arrival_sent,
    COUNT(post_play_email_sent_at) as post_play_sent,
    ROUND(COUNT(pre_arrival_email_sent_at)::numeric / COUNT(*) * 100, 1) as pre_arrival_pct,
    ROUND(COUNT(post_play_email_sent_at)::numeric / COUNT(*) * 100, 1) as post_play_pct
FROM bookings
WHERE status = 'Confirmed'
AND date >= CURRENT_DATE - INTERVAL '30 days';
```

### Email Send Times Distribution
```sql
-- When are emails being sent? (hour of day)
SELECT
    EXTRACT(HOUR FROM pre_arrival_email_sent_at) as hour_of_day,
    COUNT(*) as email_count
FROM bookings
WHERE pre_arrival_email_sent_at IS NOT NULL
GROUP BY hour_of_day
ORDER BY hour_of_day;
```

---

## 🛡️ Error Handling

The system handles:
- ✅ Missing tee times (shows "TBD")
- ✅ Invalid email addresses (SendGrid validation)
- ✅ Duplicate sends (tracking prevents resending)
- ✅ Missing configuration (graceful error messages)
- ✅ Database connection issues (exceptions with clear messages)

All functions return `(success: bool, message: str)` for easy error handling.

---

## 🔒 Production Best Practices

1. **Test in dry-run mode first**
   ```bash
   python customer_journey_marketing_logic.py both --dry-run
   ```

2. **Start with a single club**
   ```bash
   python customer_journey_marketing_logic.py both --club=streamsong
   ```

3. **Monitor SendGrid dashboard** for deliverability issues

4. **Set up email alerts** for failures:
   ```python
   sent, failed, results = process_pre_arrival_emails()
   if failed > 0:
       # Send alert to admin
       send_alert_email(f"Customer Journey: {failed} emails failed")
   ```

5. **Schedule during off-peak hours** (e.g., 9 AM instead of noon)

6. **Keep SendGrid API key secure** - use environment variables, not hardcoded

7. **Monitor database performance** - add indexes if queries are slow

---

## 📞 Support

For issues with:
- **SendGrid**: Check API key, template IDs, sender verification
- **Database**: Verify connection string, run migration, check column names
- **Tee Times**: Review extraction logic, check data format in database
- **Duplicate Emails**: Verify tracking columns exist and migration was run

---

## 📄 License

This code is provided as-is for integration into your golf booking system.

---

## 🎯 Summary

```bash
# 1. Install
pip install sendgrid psycopg pandas

# 2. Migrate
psql $DATABASE_URL < customer_journey_migration.sql

# 3. Configure environment variables
export SENDGRID_API_KEY="..."
export DATABASE_URL="..."

# 4. Test
python customer_journey_marketing_logic.py both --dry-run

# 5. Run daily (cron)
0 9 * * * python customer_journey_marketing_logic.py both --club=streamsong
```

That's it! Your automated customer journey emails are ready to go. 🎉
