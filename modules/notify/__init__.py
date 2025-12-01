"""Notify Platform Integration Module"""
import json
import requests
import pandas as pd
from datetime import datetime


def prepare_booking_data_for_export(df, format_type='json'):
    """
    Prepare booking data for export to Notify platform.
    Supports JSON, API-ready dict, and CSV formats.
    """
    export_data = []
    for _, row in df.iterrows():
        booking_record = {
            'booking_id': str(row.get('booking_id', '')),
            'customer_email': str(row.get('guest_email', '')),
            'booking_date': row['date'].strftime('%Y-%m-%d') if pd.notna(row.get('date')) else '',
            'tee_time': str(row.get('tee_time', '')),
            'players': int(row.get('players', 1)),
            'total_amount': float(row.get('total', 0)),
            'status': str(row.get('status', '')),
            'golf_courses': str(row.get('golf_courses', '')),
            'hotel_required': bool(row.get('hotel_required', False)),
            'created_at': row['timestamp'].strftime('%Y-%m-%dT%H:%M:%SZ') if pd.notna(row.get('timestamp')) else '',
            'club': str(row.get('club', ''))
        }
        export_data.append(booking_record)
    return export_data


def export_to_json(df):
    """Export booking data to JSON format for Notify platform"""
    data = prepare_booking_data_for_export(df, 'json')
    return json.dumps({
        'export_timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total_records': len(data),
        'bookings': data
    }, indent=2)


def export_to_api_format(df):
    """Export booking data in API-ready format for webhook/API integration"""
    data = prepare_booking_data_for_export(df, 'api')
    return {
        'meta': {
            'export_timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'total_records': len(data),
            'format_version': '1.0'
        },
        'data': data
    }


def push_to_notify_api(df, api_endpoint, api_key=None):
    """
    Push booking data to external Notify platform via API.
    Returns success status and response message.
    """
    try:
        payload = export_to_api_format(df)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        response = requests.post(
            api_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code in [200, 201, 202]:
            return True, f"Successfully pushed {len(payload['data'])} records to Notify platform"
        else:
            return False, f"API returned status {response.status_code}: {response.text[:200]}"
    except requests.exceptions.Timeout:
        return False, "Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to the Notify platform. Please check the endpoint URL."
    except Exception as e:
        return False, f"Error pushing to API: {str(e)}"


def export_notify_csv(df):
    """Export booking data in CSV format optimized for Notify platform import"""
    export_df = pd.DataFrame(prepare_booking_data_for_export(df, 'csv'))
    return export_df.to_csv(index=False)


__all__ = [
    'prepare_booking_data_for_export',
    'export_to_json',
    'export_to_api_format',
    'push_to_notify_api',
    'export_notify_csv'
]
