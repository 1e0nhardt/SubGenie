import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import List, NamedTuple

from deepmultilingualpunctuation import PunctuationModel
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from faster_whisper.transcribe import Word

from src.utils import CONSOLE, LOGGER, SAMPLE_RATE

warnings.filterwarnings("ignore")


@dataclass
class WhisperAsrConfig:
    # 模型名或模型文件夹路径
    whisper_model: str = "models/whisper-large-v3"
    # 预训练标点符号模型
    punctuation_model: str = "models/oliverguhr-fullstop-punctuation-multilang-large"
    # 设备
    device: str = "cuda"
    # 模型精度 float16 | int8_float16 | int8 对应 cuda | cuda| cpu
    compute_type: str = "float16"
    # 提示词，建议输入易错词
    prompt: str = "Hi, welcome to my lecture. Slay the Spire, bat, crab, cards, .tres, .tscn, tree, packed scene."
    # 任务类型 transcribe | translate
    task: str = 'transcribe'
    # 断句静音间隔
    gap_threshold: float = 0.5
    # 长句阈值
    long_sentence_threshold: int = 20
    # 需要重新标点的长句，对应的单词数/标点符号数的比例阈值
    words_mark_count_rate_threshold: int = 12


class SubtitleLine(NamedTuple):
    start: float
    end: float
    text: str


class WhisperAsr:
    def __init__(self, config: WhisperAsrConfig = WhisperAsrConfig()):
        self.config = config
        self.model = WhisperModel(config.whisper_model, device=config.device, compute_type=config.compute_type)
        self.punctuation_model = PunctuationModel(config.punctuation_model)
        self.audio_np = None
        self.audio_path = None
    
    def load_audio(self, audio_filepath: str):
        if self.audio_path == audio_filepath:
            return

        self.audio_path = audio_filepath
        self.audio_np = decode_audio(audio_filepath, SAMPLE_RATE, False)

    def transcribe_audio_full(self) -> List[SubtitleLine]:
        if self.audio_np is None:
            LOGGER.warn("No audio loaded, please call load_audio first.")
            return []

        segments, _ = self.model.transcribe(
            self.audio_np, word_timestamps=True, 
            condition_on_previous_text=False, initial_prompt=self.config.prompt)

        # transcribe
        subtitle_line_lst = []
        all_words = []
        with CONSOLE.status("[green]Transcribing..."):
            for segment in segments:
                all_words.extend(list(segment.words))

        # split sentences
        sentence_words = []
        with CONSOLE.status("[green]Splitting sentences..."):
            for i, word in enumerate(all_words):
                sentence_words.append(word)

                if word.word.endswith(".") or i == len(all_words) - 1:
                    subtitle_line_lst.extend(self.try_split_sentence(sentence_words))
                    sentence_words.clear()

        return subtitle_line_lst
    
    def try_split_sentence(self, sentence_words: List[Word]) -> List[SubtitleLine]:
        # 丢弃语气词
        if len(sentence_words) < 2:
            return []

        if len(sentence_words) < self.config.long_sentence_threshold:
            return [SubtitleLine(sentence_words[0].start, sentence_words[-1].end, get_sentence_text(sentence_words))]

        partial_sentence_list = []
        partial_start = 0
        partial_words = []
        sentence_words = self.try_punctuation(sentence_words)
        # >20 words
        for i in range(len(sentence_words) - 1):
            curr_word = sentence_words[i]
            next_word = sentence_words[i+1]
            if len(partial_words) == 0:
                partial_start = curr_word.start
            
            partial_words.append(curr_word)

            common_sentence_end = curr_word.word[-1] in ".!?"
            comma_split_situation = (len(partial_words) > 4 
                                    and curr_word.word[-1] == "," 
                                    and next_word.word.strip().lower() 
                                        in ["and", "so", "but", "or", "then", "because", "where", "we", "you"]
                                    )
            long_gap_situation = next_word.start - curr_word.end > self.config.gap_threshold
            if common_sentence_end or comma_split_situation or long_gap_situation:
                partial_sentence_list.append(SubtitleLine(partial_start, curr_word.end, get_sentence_text(partial_words)))
                partial_words.clear()
        
        partial_words.append(sentence_words[-1])
        partial_sentence_list.append(SubtitleLine(partial_start, curr_word.end, get_sentence_text(partial_words)))
        return partial_sentence_list
    
    def try_punctuation(self, sentence_words: List[Word]) -> List[Word]:
        mark_count = 0
        for word in sentence_words:
            if word.word[-1].lower() not in "abcdefghijklmnopqrstuvwxyz1234567890":
                mark_count += 1
        # LOGGER.debug(f"[blue]Mark Count: {mark_count}")
        # LOGGER.debug(f"[blue]Rate: {len(sentence_words) / mark_count}")
        if mark_count == 0 or len(sentence_words) / mark_count > self.config.words_mark_count_rate_threshold:
            raw_text = get_sentence_text(sentence_words)
            punctuation_text = self.punctuation_model.restore_punctuation(raw_text)
            # LOGGER.info("Compare")
            # LOGGER.info(f"[red]Raw: {raw_text}")
            # LOGGER.info(f"[green]Punctuation: {punctuation_text}")

            new_words = punctuation_text.split(" ")
            if len(new_words) != len(sentence_words):
                # user-friendly <--> user,-friendly | itch.io <--> itch,.io
                # pop-up.tscn <--> pop,-up,.tscn | control-alt-o <--> control,-alt,-o
                LOGGER.warn(f"Punctuation Error: {len(new_words)} != {len(sentence_words)}. Try fix.")
                i = len(sentence_words) - 1
                while i > 0:
                    if sentence_words[i].word[0] != " ":
                        sentence_words[i-1] = sentence_words[i-1]._replace(
                            end=sentence_words[i].end,
                            word=sentence_words[i-1].word + sentence_words[i].word
                        )
                        sentence_words.pop(i)
                    i -= 1
            
            if len(new_words) == len(sentence_words):
                for i, (new_text, word) in enumerate(zip(new_words, sentence_words)):
                    sentence_words[i] = word._replace(word=" " + new_text)
            else:
                LOGGER.warn(f"Punctuation Error: {len(new_words)} != {len(sentence_words)}. Fix fail.")
                CONSOLE.print(sentence_words)
        return sentence_words

    def transcribe_audio_slice(self, start_time: float, end_time: float) -> str:
        if self.audio_np is None:
            return ""

        segments, _ = self.model.transcribe(self.audio_np[int(SAMPLE_RATE*start_time):int(SAMPLE_RATE*end_time)], word_timestamps=True, condition_on_previous_text=False)

        all_words = []
        # transcribe
        for segment in segments:
            all_words.extend(list(segment.words))
        
        all_words_reduce = [(word.word, word.start + start_time, word.end + start_time) for word in all_words]
        return json.dumps(all_words_reduce)


def get_sentence_text(words: list) -> str:
    return "".join([word.word for word in words]).strip()

