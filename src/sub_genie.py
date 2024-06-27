import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import dashscope

from src.translator import Translator, TranslatorConfig
from src.utils import (ASS_TEMPLAT, CONSOLE, LOGGER, extract_sound_from_video,
                       filter_files, get_timestamp)
from src.whisper_asr import WhisperAsr, WhisperAsrConfig
from src.youtube_downloader import DownloadConfig, YoutubeDownloader

warnings.filterwarnings('ignore')


@dataclass
class SubGenieConfig:
    """SubGenie, 一个双语字幕生成工具"""

    # 任务类型(download | generate | continue)
    task: str = 'generate'
    # 输入视频目录
    video_dir: str = "assets/video"
    # 视频过滤器
    video_filter: str = 'mp4,mkv'
    # 音频目录
    audio_dir: str = "assets/audio"
    # 音频过滤器
    audio_filter: str = 'mp3,wav,flac,m4a,aac'
    # ASR输出目录
    asr_dir: str = "assets/asr_output"
    # ASR输出文件过滤器
    asr_filter: str = 'list'
    # 输出字幕文件类型 srt | ass
    subtitle_type: str = 'ass'
    # 直接从已有音频开始，不需要从视频中提取这一步
    input_is_audio: bool = False
    # 只保留目标语言
    only_tgt: bool = False
    # 语音转文字后不翻译(手动用ChatGPT翻译)
    skip_translate: bool = False
    # 语音转文字配置
    whisper_asr: WhisperAsrConfig = field(default_factory=WhisperAsrConfig)
    # 翻译配置
    translator: TranslatorConfig = field(default_factory=TranslatorConfig)
    # Youtube下载配置
    youtube_downloader: DownloadConfig = field(default_factory=DownloadConfig)


class SubGenie:
    def __init__(self, config: SubGenieConfig = SubGenieConfig()):
        self.config = config
        self._check_config()
        self.translator = Translator(config.translator)
        self.whisper_asr = WhisperAsr(config.whisper_asr)
    
    def download_video(self):
        downloader = YoutubeDownloader(self.config.youtube_downloader)
        downloader.run()
    
    def batch_generate(self):
        """
        批量处理视频文件，包括提取音频、语音转文字和字幕翻译。
        
        首先，根据配置的过滤条件筛选出视频、音频和字幕文件。
        如果配置中指定输入不是音频且视频对应音频不存在，则从视频中提取音频。
        然后，对音频文件进行语音转文字处理，将结果写入.srt或.ass格式的字幕文件。
        最后，对未翻译的字幕文件进行翻译，并将翻译结果写入相应的视频目录中。
        """
        # 根据指定的后缀筛选视频、音频和字幕文件
        video_files = filter_files(self.video_dir, self.config.video_filter)
        audio_files = filter_files(self.audio_dir, self.config.audio_filter)
        asr_output_files = filter_files(self.asr_output_dir, self.config.asr_filter)

        # 如果配置中指定输入不是音频，则从视频中提取音频
        if not self.config.input_is_audio:
            # 从视频文件中筛选出未对应音频文件的视频
            video_files_need_extract = list(filter(lambda x: x.stem not in [f.stem for f in audio_files], video_files))
            CONSOLE.rule('提取音频')
            for file in video_files_need_extract:
                CONSOLE.print(f'[green]提取音频: {file.name}')
                extracted_audio_path = self.audio_dir / (file.stem + '.wav')
                extract_sound_from_video(file, extracted_audio_path)
                audio_files.append(extracted_audio_path)
        
        CONSOLE.rule('语音转文字')
        def filter_audio_file(file: Path) -> bool:
            return (file.stem not in [f.stem for f in asr_output_files] 
                    and file.stem in [f.stem for f in video_files])
        audio_files = list(filter(filter_audio_file, audio_files))
        for file in audio_files:
            CONSOLE.print(f'[green]语音转文字: {file.as_posix()}')
            self.whisper_asr.load_audio(file.as_posix())
            subtitle_line_lst = self.whisper_asr.transcribe_audio_full()
            asr_output_path = self.asr_output_dir / (file.stem + '.list')
            with asr_output_path.open("w", encoding="utf-8") as f:
                for line in subtitle_line_lst:
                    f.write("[%.2f->%.2f]%s\n" % (line.start, line.end, line.text))
            asr_output_files.append(asr_output_path)

        translated_files = filter_files(self.video_dir, "srt,ass")
        def filter_list_file(file: Path) -> bool:
            return (file.stem not in [f.stem for f in translated_files] 
                    and file.stem in [f.stem for f in video_files])
        asr_output_files = list(filter(filter_list_file, asr_output_files))
        if self.config.skip_translate or not dashscope.api_key:
            if not dashscope.api_key:
                LOGGER.warning("Dashscope api key not set, skip translate")
            for file in asr_output_files:
                if not file.with_stem(file.stem + "_zh").exists():
                    with file.with_stem(file.stem + "_zh").open("w", encoding="utf-8") as f:
                        f.write("")
            return

        CONSOLE.rule('字幕翻译')
        for file in asr_output_files:
            if file.stem.endswith("_zh"):
                continue
            CONSOLE.print(f'[green]字幕翻译: {file.name}')
            self._write_subtitle(
                self.translator.translate_file(file), 
                self.video_dir / (file.stem + '.' + self.config.subtitle_type)
            )
    
    def continue_generate(self):
        """
        继续处理视频文件，包括从字幕文件中提取翻译结果并写入视频目录中。
        
        首先，根据指定的过滤条件筛选出字幕文件。
        然后，将翻译结果合并并生成字幕文件。
        """
        translated_files = list(self.asr_output_dir.glob("*_zh.list"))
        for file in translated_files:
            raw_file = file.with_stem(file.stem[:-3])
            if not raw_file.exists():
                continue

            final_srt_path = self.video_dir / (raw_file.stem + '.' + self.config.subtitle_type)
            if final_srt_path.exists():
                continue

            CONSOLE.print(f'[green]合并翻译结果: {file.name}')
            with file.open("r", encoding="utf-8") as f:
                translation = f.read().strip()
            with raw_file.open("r", encoding="utf-8") as f:
                raw_line_lst = f.read().strip().splitlines()

            # final_srt_path = self.video_dir / (raw_file.stem + '.' + self.config.subtitle_type)
            # self._write_ass_subtitle(raw_line_lst, translation.splitlines(), final_srt_path)
            
            # 合并翻译结果
            pattern = re.compile(r"\[\d+\.\d+->\d+\.\d+\]")
            translated_subtitles = re.split(pattern, translation)[1:]
            if len(translated_subtitles) != len(raw_line_lst):
                CONSOLE.print(f'[red]翻译结果数量不匹配: {file.name}')
                continue
            
            for i in range(len(raw_line_lst)):
                raw_line_lst[i] = raw_line_lst[i].strip() + r"@@@" + \
                    translated_subtitles[i].strip() + "\n"

            self._write_subtitle(raw_line_lst, final_srt_path)
    
    # 利用ass格式的能力，将中英字幕分开写。可以避免AI翻译吞行导致的错位。
    def _write_ass_subtitle(self, en_line_lst, zh_line_lst, srt_path):
        if srt_path.suffix != '.ass':
            return
        
        pattern = re.compile(r"^\[(\d+\.\d+)->(\d+\.\d+)\](.*)$")
        line_format_zh = "Dialogue: %d,%s,%s,ZH,,0,0,0,,%s\n"
        line_format_en = "Dialogue: %d,%s,%s,EN,,0,0,0,,%s\n"
        with srt_path.open("w", encoding="utf-8") as f:
            if srt_path.suffix == '.ass':
                f.write(ASS_TEMPLAT)
            
            for line in en_line_lst: # 文件中先出现的显示在下。
                if line == "":
                    continue

                match = pattern.match(line.strip())
                if match is None:
                    # API翻译结果有时候会出现"\u200b"，导致正则匹配失败，去掉再试一次。
                    line = line.replace("\u200b", "") 
                    match = pattern.match(line.strip())
                    if match is None:
                        CONSOLE.print("[red]匹配失败: %s" % line)
                        continue
                start, end, text = match.groups()
                f.write(line_format_en % (0, get_timestamp(start), get_timestamp(end), text))

            for line in zh_line_lst:
                if line == "":
                    continue

                match = pattern.match(line.strip())
                if match is None:
                    # API翻译结果有时候会出现"\u200b"，导致正则匹配失败，去掉再试一次。
                    line = line.replace("\u200b", "") 
                    match = pattern.match(line.strip())
                    if match is None:
                        CONSOLE.print("[red]匹配失败: %s" % line)
                        continue
                start, end, text = match.groups()
                f.write(line_format_zh % (0, get_timestamp(start), get_timestamp(end), text))


    def _write_subtitle(self, translated_line_lst, srt_path):
        pattern = re.compile(r"^\[(\d+\.\d+)->(\d+\.\d+)\](.*)@@@(.*)$")
        if srt_path.suffix == '.ass':
            if self.config.only_tgt:
                line_format = "Dialogue: %d,%s,%s,ZH,,0,0,0,,%s\n"
            else:
                line_format = "Dialogue: %d,%s,%s,ZH,,0,0,0,,%s\\N{\\rEN}%s\n"
        else:
            if self.config.only_tgt:
                line_format = "%d\n%s --> %s\n%s\n\n"
            else:
                line_format = "%d\n%s --> %s\n%s\n%s\n\n"

        with srt_path.open("w", encoding="utf-8") as f:
            if srt_path.suffix == '.ass':
                f.write(ASS_TEMPLAT)

            for i, line in enumerate(translated_line_lst):
                if line == "":
                    continue
                if srt_path.suffix == '.ass':
                    line_id = 0
                else:
                    line_id = i + 1

                match = pattern.match(line.strip())
                if match is None:
                    # API翻译结果有时候会出现"\u200b"，导致正则匹配失败，去掉再试一次。
                    line = line.replace("\u200b", "") 
                    match = pattern.match(line.strip())
                    if match is None:
                        CONSOLE.print("[red]匹配失败: %s" % line)
                        continue
                start, end, source_text, target_text = match.groups()
                if self.config.only_tgt:
                    f.write(line_format % (line_id, get_timestamp(start), get_timestamp(end), target_text))
                else:
                    f.write(line_format % (line_id, get_timestamp(start), get_timestamp(end), target_text, source_text))

    @property
    def video_dir(self):
        return Path(self.config.video_dir)
    
    @property
    def audio_dir(self):
        return Path(self.config.audio_dir)

    @property
    def asr_output_dir(self): 
        return Path(self.config.asr_dir)

    def _check_config(self):
        def ensure_dir(dir_path):
            dpath = Path(dir_path)
            if not dpath.exists():
                dpath.mkdir(parents=True, exist_ok=True)
        
        ensure_dir(self.config.video_dir)
        ensure_dir(self.config.audio_dir)
        ensure_dir(self.config.asr_dir)
