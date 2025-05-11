import os
import time
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import re
import json
import dotenv

# Configuration
dotenv.load_dotenv()  # Load environment variables from .env file
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # Your YouTube Data API key
PLAYLIST_ID = os.getenv("PLAYLIST_ID")  # YouTube playlist ID
TRANSCRIPTS_DIR = os.path.join("backend", "transcripts")
RAW_DIR = os.path.join(TRANSCRIPTS_DIR, "raw")
CLEAN_DIR = os.path.join(TRANSCRIPTS_DIR, "clean")

# Create directories if they don't exist
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CLEAN_DIR, exist_ok=True)

def get_playlist_videos(playlist_id, api_key):
    """Get all video IDs and titles from a YouTube playlist."""
    # Clean playlist ID - remove any query parameters
    if '&' in playlist_id:
        playlist_id = playlist_id.split('&')[0]
    print(f"Using cleaned playlist ID: {playlist_id}")
    """Get all video IDs and titles from a YouTube playlist."""
    youtube = build("youtube", "v3", developerKey=api_key)
    
    videos = []
    next_page_token = None
    
    while True:
        # Get batch of playlist items
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        
        # Process each video in the current batch
        for item in playlist_response["items"]:
            video_id = item["snippet"]["resourceId"]["videoId"]
            video_title = item["snippet"]["title"]
            video_position = item["snippet"]["position"]
            
            videos.append({
                "id": video_id,
                "title": video_title,
                "position": video_position + 1  # Make 1-indexed for readability
            })
        
        # Check if there are more pages
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break
    
    # Sort videos by their position in the playlist
    videos.sort(key=lambda x: x["position"])
    return videos

def get_transcript(video_id):
    """Get transcript for a video in Hindi language."""
    try:
        # Try to get transcript in Hindi
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi'])
        return transcript
    except Exception as e:
        try:
            # If Hindi fails, try to get auto-generated Hindi transcript
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi-IN'])
            return transcript
        except Exception as e2:
            try:
                # If that fails, try to get any available transcript
                transcript = YouTubeTranscriptApi.get_transcript(video_id)
                return transcript
            except Exception as e3:
                print(f"Could not get transcript for video {video_id}: {str(e3)}")
                return None

def clean_transcript(transcript):
    """Clean transcript by removing timestamps and merging text."""
    if not transcript:
        return ""
    
    # Format transcript - join all text entries
    text_parts = [entry['text'] for entry in transcript]
    formatted_transcript = "\n".join(text_parts)
    
    # Additional cleaning if needed
    clean_text = formatted_transcript.strip()
    
    # Remove any [Music] or [Applause] type markers
    clean_text = re.sub(r'\[[^\]]+\]', '', clean_text)
    
    return clean_text

def save_transcript(video_info, transcript, raw_dir, clean_dir):
    """Save both raw and cleaned transcript."""
    video_id = video_info["id"]
    position = video_info["position"]
    
    # Create safe filename from position and title
    safe_title = re.sub(r'[^\w\s-]', '', video_info["title"]).strip().replace(' ', '_')
    base_filename = f"{position:03d}_{safe_title}_{video_id}"
    
    # Save raw transcript as JSON
    if transcript:
        raw_path = os.path.join(raw_dir, f"{base_filename}.json")
        with open(raw_path, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, ensure_ascii=False, indent=2)
        
        # Save cleaned transcript as text
        clean_text = clean_transcript(transcript)
        clean_path = os.path.join(clean_dir, f"{base_filename}.txt")
        with open(clean_path, 'w', encoding='utf-8') as f:
            f.write(clean_text)
        
        return True
    return False

def main():
    print(f"Fetching videos from playlist: {PLAYLIST_ID}")
    videos = get_playlist_videos(PLAYLIST_ID, YOUTUBE_API_KEY)
    print(f"Found {len(videos)} videos in the playlist")
    
    successful = 0
    failed = 0
    
    for i, video in enumerate(videos):
        print(f"Processing {i+1}/{len(videos)}: {video['title']} (ID: {video['id']})")
        
        try:
            # Get transcript
            transcript = get_transcript(video['id'])
            
            # Save transcript
            if transcript:
                success = save_transcript(video, transcript, RAW_DIR, CLEAN_DIR)
                if success:
                    successful += 1
                    print(f"✓ Saved transcript")
                else:
                    failed += 1
                    print(f"✗ Failed to save transcript")
            else:
                failed += 1
                print(f"✗ No transcript available")
        except Exception as e:
            failed += 1
            print(f"✗ Error processing video: {e}")
        
        # Sleep to avoid hitting API rate limits
        time.sleep(1)
    
    print(f"\nSummary:")
    print(f"- Successfully saved transcripts: {successful}")
    print(f"- Failed to save transcripts: {failed}")
    print(f"- Total videos processed: {successful + failed}")
    print(f"\nTranscripts saved to:")
    print(f"- Raw transcripts: {os.path.abspath(RAW_DIR)}")
    print(f"- Clean transcripts: {os.path.abspath(CLEAN_DIR)}")

if __name__ == "__main__":
    main()