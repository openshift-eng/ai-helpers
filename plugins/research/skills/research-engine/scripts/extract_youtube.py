#!/usr/bin/env python3
"""Extract transcripts from YouTube videos using yt-dlp."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def parse_vtt_to_text(vtt_content: str) -> str:
    """Convert VTT subtitle format to plain text."""
    lines = []
    seen = set()
    
    for line in vtt_content.split('\n'):
        # Skip VTT header, timestamps, and empty lines
        if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            continue
        if re.match(r'^\d{2}:\d{2}:\d{2}', line):
            continue
        if '-->' in line:
            continue
        if not line.strip():
            continue
        
        # Remove HTML tags and clean up
        cleaned = re.sub(r'<[^>]+>', '', line).strip()
        
        # Skip duplicates (YouTube often repeats lines)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            lines.append(cleaned)
    
    return ' '.join(lines)


def extract_youtube(url: str, output_dir: str) -> dict:
    """Extract transcript from a YouTube video.
    
    Args:
        url: YouTube URL
        output_dir: Directory to save extracted transcript
        
    Returns:
        dict with extraction result
    """
    # Check for yt-dlp
    if not shutil.which("yt-dlp"):
        return {
            "success": False,
            "error": "yt-dlp not installed. Run: pip install yt-dlp",
            "url": url,
        }
    
    video_id = extract_video_id(url)
    if not video_id:
        return {
            "success": False,
            "error": f"Could not extract video ID from URL: {url}",
            "url": url,
        }
    
    print(f"Extracting transcript for video: {video_id}", file=sys.stderr)
    
    # Create temp directory for subtitles
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download subtitles using yt-dlp
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--output", f"{temp_dir}/%(id)s.%(ext)s",
            url,
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout while fetching subtitles",
                "url": url,
            }
        
        # Find the subtitle file
        subtitle_file = None
        for f in Path(temp_dir).glob("*.vtt"):
            subtitle_file = f
            break
        
        if not subtitle_file:
            # Try to get video info for error message
            info_cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                url,
            ]
            
            try:
                info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
                if info_result.returncode == 0:
                    info = json.loads(info_result.stdout)
                    title = info.get("title", "Unknown")
                    return {
                        "success": False,
                        "error": f"No English captions available for: {title}",
                        "url": url,
                        "video_id": video_id,
                    }
            except:
                pass
            
            return {
                "success": False,
                "error": "No subtitles/captions available for this video",
                "url": url,
                "video_id": video_id,
            }
        
        # Read and parse VTT content
        with open(subtitle_file, "r", encoding="utf-8") as f:
            vtt_content = f.read()
        
        transcript = parse_vtt_to_text(vtt_content)
        
        if not transcript:
            return {
                "success": False,
                "error": "Subtitle file was empty or could not be parsed",
                "url": url,
                "video_id": video_id,
            }
    
    # Get video metadata
    info_cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        url,
    ]
    
    title = f"YouTube Video {video_id}"
    channel = "Unknown"
    duration = 0
    
    try:
        info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
        if info_result.returncode == 0:
            info = json.loads(info_result.stdout)
            title = info.get("title", title)
            channel = info.get("channel", info.get("uploader", channel))
            duration = info.get("duration", 0)
    except:
        pass
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create output file
    output_file = output_path / f"{video_id}.md"
    
    content = f"""---
source_type: youtube
source_url: {url}
source_title: "{title.replace('"', "'")}"
video_id: {video_id}
channel: "{channel.replace('"', "'")}"
duration_seconds: {duration}
extracted_at: {datetime.now(timezone.utc).isoformat()}
---

# {title}

**Channel**: {channel}
**Duration**: {duration // 60}:{duration % 60:02d}
**Video**: https://youtube.com/watch?v={video_id}

## Transcript

{transcript}
"""
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Extracted to: {output_file}", file=sys.stderr)
    
    return {
        "success": True,
        "url": url,
        "video_id": video_id,
        "title": title,
        "channel": channel,
        "duration_seconds": duration,
        "output_file": str(output_file),
        "transcript_length": len(transcript),
        "word_count": len(transcript.split()),
    }


def main():
    parser = argparse.ArgumentParser(description="Extract YouTube transcripts")
    parser.add_argument("--url", required=True, help="YouTube URL")
    parser.add_argument("--output", required=True, help="Output directory")
    
    args = parser.parse_args()
    
    result = extract_youtube(args.url, args.output)
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()


