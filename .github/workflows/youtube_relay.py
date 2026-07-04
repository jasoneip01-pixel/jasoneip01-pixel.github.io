#!/usr/bin/env python3
"""YouTube Relay — fetches page metadata from GH US runner, saves plain text.
Triggered by workflow_dispatch with URL input."""

import json, os, re, html, sys
from datetime import datetime, timezone
try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], check=True)
    import requests

OUT = f"data/youtube/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (X11; Linux x86_64) YouTubeRelay/1.0'

# Check for workflow_dispatch URL input
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--url', help='Specific YouTube URL to fetch', default='')
args = parser.parse_args()

def extract_initial_data(html_text):
    """Extract ytInitialData from YouTube page."""
    m = re.search(r'var ytInitialData\s*=\s*(\{.+?\});\s*\n\s*</script>', html_text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    return None

def extract_meta(html_text):
    """Extract OG meta tags."""
    meta = {}
    for m in re.finditer(r'<meta\s+(?:name|property)="([^"]+)"\s+content="([^"]*)"', html_text):
        meta[m.group(1)] = m.group(2)
    return meta

urls = []
if args.url:
    urls.append(args.url)
else:
    # Default: fetch trending content (no URL specified → skip)
    print("No URL provided. Use workflow_dispatch with 'url' input.")
    sys.exit(0)

for url in urls:
    vid_id = None
    if 'watch?v=' in url:
        vid_id = url.split('watch?v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        vid_id = url.split('youtu.be/')[1].split('?')[0]
    
    slug = vid_id or url.split('/')[-1][:20]
    
    try:
        print(f"Fetching: {url}")
        r = requests.get(url, headers={'User-Agent': UA, 'Accept': 'text/html'}, timeout=20)
        
        result = {
            'url': url,
            'video_id': vid_id,
            'status_code': r.status_code,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'response_size': len(r.text),
        }
        
        # Try ytInitialData first (best source)
        data = extract_initial_data(r.text)
        if data:
            try:
                vd = data['contents']['twoColumnWatchNextResults']['results']['results']['contents']
                for section in vd:
                    if 'videoPrimaryInfoRenderer' in section:
                        p = section['videoPrimaryInfoRenderer']
                        result['title'] = p.get('title', {}).get('runs', [{}])[0].get('text', '')
                        result['views'] = p.get('viewCount', {}).get('videoViewCountRenderer', {}).get('viewCount', {}).get('simpleText', '')
                        result['published'] = p.get('dateText', {}).get('simpleText', '')
                    if 'videoSecondaryInfoRenderer' in section:
                        s = section['videoSecondaryInfoRenderer']
                        result['channel'] = s.get('owner', {}).get('videoOwnerRenderer', {}).get('title', {}).get('runs', [{}])[0].get('text', '')
                        result['subscribers'] = s.get('owner', {}).get('videoOwnerRenderer', {}).get('subscriberCountText', {}).get('simpleText', '')
                        desc_runs = s.get('description', {}).get('runs', [])
                        result['description'] = ' '.join([r.get('text', '') for r in desc_runs])[:3000]
            except Exception as e:
                result['data_error'] = str(e)[:200]
        
        # Fallback: OG meta
        if 'title' not in result:
            meta = extract_meta(r.text)
            result['title'] = meta.get('og:title', '')
            result['description'] = meta.get('og:description', '')[:3000]
        
        # Extract comments (top-level)
        if data:
            try:
                comments = []
                for c in data.get('engagementPanels', []):
                    for item in c.get('engagementPanelSectionListRenderer', {}).get('content', {}).get('items', []):
                        for thread in item.get('continuationItems', []):
                            cr = thread.get('commentThreadRenderer', {}).get('comment', {}).get('commentRenderer', {})
                            if cr:
                                comments.append({
                                    'author': cr.get('authorText', {}).get('simpleText', ''),
                                    'text': ''.join([t.get('text','') for t in cr.get('contentText', {}).get('runs', [])])[:500],
                                    'likes': cr.get('voteCount', {}).get('simpleText', ''),
                                })
                if comments:
                    result['comments'] = comments[:10]
            except:
                pass
        
        path = f"{OUT}/{slug}.json"
        with open(path, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"  ✅ {slug}.json — {len(r.text)} bytes → {result.get('title','?')[:80]}")
        
    except Exception as e:
        path = f"{OUT}/{slug}.json"
        with open(path, 'w') as f:
            json.dump({'url': url, 'error': str(e)[:300]}, f, indent=2, ensure_ascii=False)
        print(f"  ❌ {slug}: {e}")

print(f"\nDone. Saved to {OUT}/")
