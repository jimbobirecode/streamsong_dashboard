"""Analytics Helper Functions Module"""
import pandas as pd


def calculate_lead_times(df):
    """Calculate average lead time between inquiry and booking"""
    lead_times = []

    for _, row in df.iterrows():
        if pd.notna(row.get('timestamp')) and pd.notna(row.get('date')):
            lead_time = (row['date'] - row['timestamp']).days
            if lead_time >= 0:
                lead_times.append({
                    'booking_id': row['booking_id'],
                    'lead_time_days': lead_time,
                    'status': row['status']
                })

    return pd.DataFrame(lead_times)


def calculate_customer_inquiry_frequency(df):
    """Calculate booking inquiry frequency by customer for targeted marketing"""
    customer_stats = df.groupby('guest_email').agg({
        'booking_id': 'count',
        'total': 'sum',
        'players': 'sum',
        'status': lambda x: (x == 'Booked').sum()
    }).reset_index()

    customer_stats.columns = ['Customer Email', 'Total Inquiries', 'Total Revenue',
                              'Total Players', 'Completed Bookings']

    customer_stats['Conversion Rate'] = (
        customer_stats['Completed Bookings'] / customer_stats['Total Inquiries'] * 100
    ).round(1)

    customer_stats['Avg Booking Value'] = (
        customer_stats['Total Revenue'] / customer_stats['Total Inquiries']
    ).round(2)

    return customer_stats.sort_values('Total Inquiries', ascending=False)


def calculate_golf_course_popularity(df):
    """Calculate booking statistics by golf course"""
    course_df = df[df['golf_courses'].notna() & (df['golf_courses'] != '')]

    if course_df.empty:
        return pd.DataFrame()

    course_stats = course_df.groupby('golf_courses').agg({
        'booking_id': 'count',
        'total': 'sum',
        'players': 'sum',
        'status': lambda x: (x == 'Booked').sum()
    }).reset_index()

    course_stats.columns = ['Golf Course', 'Total Requests', 'Total Revenue',
                            'Total Players', 'Confirmed Bookings']

    course_stats['Conversion Rate'] = (
        course_stats['Confirmed Bookings'] / course_stats['Total Requests'] * 100
    ).round(1)
    course_stats['Avg Revenue per Request'] = (
        course_stats['Total Revenue'] / course_stats['Total Requests']
    ).round(2)

    return course_stats.sort_values('Total Requests', ascending=False)


def identify_marketing_segments(df):
    """
    Identify marketing segments including frequent non-booking leads.
    Returns segmented customer data for targeted campaigns.
    """
    customer_stats = df.groupby('guest_email').agg({
        'booking_id': 'count',
        'total': 'sum',
        'status': lambda x: list(x),
        'timestamp': 'max'
    }).reset_index()

    customer_stats.columns = ['Customer Email', 'Total Contacts', 'Total Revenue',
                              'Statuses', 'Last Contact']

    customer_stats['Completed Bookings'] = customer_stats['Statuses'].apply(
        lambda x: sum(1 for s in x if s == 'Booked')
    )

    segments = []
    for _, row in customer_stats.iterrows():
        total_contacts = row['Total Contacts']
        completed = row['Completed Bookings']
        revenue = row['Total Revenue']

        if total_contacts >= 3 and completed == 0:
            segment = 'Frequent Non-Booker'
            priority = 'High'
            action = 'Targeted re-engagement campaign'
        elif total_contacts >= 2 and completed == 0:
            segment = 'Repeat Inquirer'
            priority = 'Medium'
            action = 'Follow-up offer campaign'
        elif completed > 0 and revenue > 500:
            segment = 'High-Value Customer'
            priority = 'VIP'
            action = 'Loyalty rewards program'
        elif completed > 0:
            segment = 'Converted Customer'
            priority = 'Standard'
            action = 'Retention campaign'
        else:
            segment = 'Single Inquiry'
            priority = 'Low'
            action = 'General marketing list'

        segments.append({
            'Customer Email': row['Customer Email'],
            'Total Contacts': total_contacts,
            'Completed Bookings': completed,
            'Total Revenue': revenue,
            'Last Contact': row['Last Contact'],
            'Segment': segment,
            'Priority': priority,
            'Recommended Action': action
        })

    return pd.DataFrame(segments)


__all__ = [
    'calculate_lead_times',
    'calculate_customer_inquiry_frequency',
    'calculate_golf_course_popularity',
    'identify_marketing_segments'
]
