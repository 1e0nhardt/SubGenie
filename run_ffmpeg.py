import subprocess
from pathlib import Path

from src.utils import TIME_RECORDER

if __name__ == '__main__':
    video_dir = Path("assets/video")
    TIME_RECORDER.reset()
    for video in video_dir.glob("*.mp4"):
        filename = video.stem
        if filename.startswith("000"):
            # cmd = f'ffmpeg -i "assets/video/{filename}.mp4" -vf subtitles="assets/video/{filename}.ass" -b:v 6M "assets/final/{filename}.mp4"'
            # 使用 NVIDIA GPU 加速
            cmd = f'ffmpeg -hide_banner -i "assets/video/{filename}.mp4" -vcodec h264_nvenc -vf subtitles="assets/video/{filename}.ass" -b:v 6M "assets/final/{filename}.mp4"'
            subprocess.run(cmd, shell=True)
            TIME_RECORDER.record(filename)
    TIME_RECORDER.show()
