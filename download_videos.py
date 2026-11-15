import os

queries = [
    ('north_lane.mp4', 'ytsearch1:heavy traffic intersection top view CCTV'),
    ('south_lane.mp4', 'ytsearch1:highway traffic congestion cars overhead'),
    ('east_lane.mp4', 'ytsearch1:rush hour busy city intersection traffic camera'),
    ('west_lane.mp4', 'ytsearch1:traffic jam cars road surveillance feed'),
]

for name, query in queries:
    print(f"Downloading {name}...")
    os.system(f'python -m yt_dlp "{query}" -f "bestvideo[height<=720][ext=mp4]/best[ext=mp4]" --match-filter "duration < 900" -o "backend/test_videos/{name}"')
