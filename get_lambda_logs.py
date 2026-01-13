"""Fetch recent Lambda logs"""
import boto3
from datetime import datetime, timedelta

client = boto3.client('logs', region_name='us-east-1')

log_group = '/aws/lambda/cti-scraper-dev-scraper'

# Get recent log streams
streams = client.describe_log_streams(
    logGroupName=log_group,
    orderBy='LastEventTime',
    descending=True,
    limit=3
)

print(f"Found {len(streams['logStreams'])} recent log streams\n")

# Get events from the most recent streams
for stream in streams['logStreams']:
    stream_name = stream['logStreamName']
    print(f"\n{'='*80}")
    print(f"Stream: {stream_name}")
    if 'lastEventTime' in stream:
        print(f"Last event: {datetime.fromtimestamp(stream['lastEventTime']/1000)}")
    print(f"{'='*80}\n")

    # Get log events
    try:
        events = client.get_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            startFromHead=True,
            limit=100
        )

        for event in events['events']:
            timestamp = datetime.fromtimestamp(event['timestamp']/1000)
            message = event['message']
            print(f"[{timestamp}] {message}")

    except Exception as e:
        print(f"Error reading stream: {e}")
