#!/usr/bin/env python3
"""
Fix Tee Times Script
This script extracts tee times from the note field (email content)
and updates the tee_time field in the bookings table.
"""

import os
import re
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")

def extract_tee_time(note_content):
    """
    Extract tee time from email content.
    Looks for patterns like:
    - Time: 12:20 PM
    - Time: 10:30 AM
    - Time: 3:45 PM
    """
    if not note_content:
        return None

    # Pattern to match "Time: HH:MM AM/PM"
    patterns = [
        r'Time:\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])',  # Time: 12:20 PM
        r'time:\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])',  # time: 12:20 pm (case insensitive)
        r'Tee\s+Time:\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])',  # Tee Time: 12:20 PM
    ]

    for pattern in patterns:
        match = re.search(pattern, note_content, re.IGNORECASE)
        if match:
            tee_time = match.group(1).strip()
            # Normalize to uppercase (12:20 PM)
            return tee_time.upper()

    return None


def update_tee_times():
    """Update all bookings with missing tee times by extracting from note field"""
    try:
        conn = psycopg.connect(DATABASE_URL)
        cursor = conn.cursor(row_factory=dict_row)

        # Get all bookings with missing or "Not Specified" tee times
        cursor.execute("""
            SELECT id, booking_id, note, tee_time
            FROM bookings
            WHERE tee_time IS NULL OR tee_time = 'Not Specified' OR tee_time = '';
        """)

        bookings = cursor.fetchall()

        if not bookings:
            print("✅ No bookings need tee time updates")
            cursor.close()
            conn.close()
            return

        print(f"Found {len(bookings)} bookings with missing tee times")
        print("-" * 60)

        updated_count = 0
        not_found_count = 0

        for booking in bookings:
            booking_id = booking['booking_id']
            note = booking['note']
            current_tee_time = booking['tee_time']

            # Try to extract tee time from note
            extracted_time = extract_tee_time(note)

            if extracted_time:
                # Update the booking
                cursor.execute("""
                    UPDATE bookings
                    SET tee_time = %s
                    WHERE id = %s;
                """, (extracted_time, booking['id']))

                print(f"✅ {booking_id}: Updated tee_time to '{extracted_time}'")
                updated_count += 1
            else:
                print(f"⚠️  {booking_id}: Could not extract tee time from note")
                not_found_count += 1

        # Commit all updates
        conn.commit()

        print("-" * 60)
        print(f"Summary:")
        print(f"  ✅ Updated: {updated_count}")
        print(f"  ⚠️  Not found: {not_found_count}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("Tee Time Extraction and Update Script")
    print("=" * 60)
    update_tee_times()
    print("=" * 60)
    print("✅ Script completed")
