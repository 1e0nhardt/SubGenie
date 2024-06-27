import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import dashscope
from deep_translator import BaiduTranslator, GoogleTranslator, constants
from deep_translator.base import BaseTranslator

from src.utils import API_USAGE_RECORDER, qwen_translate

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

LANGUAGE_CHARACTER_LIMIT = {
    "english": 4500,
    "japanese": 1600,
}


@dataclass
class TranslatorConfig:
    """翻译配置"""

    # 使用的翻译api google | baidu | qwen
    translate_api: str = 'qwen'
    baidu_appid: str = ''
    baidu_appkey: str = ''
    # 翻译源语言
    src_lang: str = 'english'
    # 翻译目标语言
    tgt_lang: str = 'chinese'
    # qwen专用。每次调用API时输入的字幕行数。
    line_num_in_one_call: int = 8
    # 通义千问模型
    qwen_model: str = 'qwen-turbo'


class Translator:
    def __init__(self, config: TranslatorConfig = TranslatorConfig()):
        self.config = config

    @property
    def character_limit(self) -> int:
        return LANGUAGE_CHARACTER_LIMIT.get(self.config.src_lang, 999)

    @property
    def source_language(self) -> str:
        return self._get_language_code(self.config.src_lang, "en")

    @property
    def target_language(self) -> str:
        if self.config.tgt_lang == "chinese":
            self.config.tgt_lang = "chinese (simplified)"

        return self._get_language_code(self.config.tgt_lang, "zh")

    def _get_language_code(self, language: str, default: str) -> str:
        """获取语言缩写码"""
        if self.config.translate_api == "google":
            return constants.GOOGLE_LANGUAGES_TO_CODES.get(language, default)
        elif self.config.translate_api == "baidu":
            return constants.BAIDU_LANGUAGE_TO_CODE.get(language, default)
        else:
            raise ValueError(
                "Invalid translate_api value. Please choose 'google' or 'baidu'.")

    @property
    def translator(self) -> BaseTranslator:
        if self.config.translate_api == "google":
            return GoogleTranslator(source=self.source_language, target=self.target_language)
        elif self.config.translate_api == "baidu":
            return BaiduTranslator(
                source=self.config.source_language, target=self.target_language,
                appid=self.config.baidu_appid, appkey=self.config.baidu_appkey)
        else:
            raise ValueError(
                "Invalid translate_api value. Please choose 'google' or 'baidu'.")

    def translate(self, subtitle: str) -> str:
        return self.translator.translate(subtitle)

    def translate_file(self, asr_output_file: Path) -> list:
        """
        翻译文件，asr_output_file文件格式如下:\n  
        [0.00->2.46]some text\n  
        [2.56->6.10]another text\n 
        ...\n 
        [46.10->48.02]yet another text\n 

        return ["[0.00->2.46]some text@@@一些文本", ..., "[46.10->48.02]yet another text@@@另一些文本"]
        """
        pattern = re.compile(r"\[\d+\.\d+->\d+\.\d+\]")
        print(f"Translating {asr_output_file}")

        translated_subtitles = []
        text_lines= []

        def batch_translate(subs):
            translation = self.translator.translate(''.join(subs))
            translated_subtitles.extend(re.split(pattern, translation)[1:])
            trl = len(translated_subtitles)
            if trl != i + 1:  # 翻译API自动合并短句导致翻译结果数量和原文字幕数量不一致。
                translated_subtitles.extend(["翻译结果数量不匹配，请检查。"]*(i+1-trl))
                print(f"翻译结果数量不匹配: {trl} -- {i + 1}.")

        with asr_output_file.open("r", encoding="utf-8") as f:
            text_lines = f.readlines()

            if self.config.translate_api == "qwen":
                for i in range(0, len(text_lines), self.config.line_num_in_one_call):
                    qwen_result = qwen_translate("\n".join(text_lines[i:i+self.config.line_num_in_one_call]), self.config.qwen_model)
                    qwen_lst = re.split(pattern, qwen_result)[1:]
                    
                    if len(qwen_lst) > self.config.line_num_in_one_call: # AI有可能编出不存在的内容
                        qwen_lst = qwen_lst[:self.config.line_num_in_one_call]

                    if len(qwen_lst) < self.config.line_num_in_one_call:
                        qwen_result_lst = list(filter(lambda x: x != "", qwen_result.splitlines()))
                        time_pattern = re.compile(r"^\[(\d+\.\d+->\d+\.\d+)\](.*)$")
                        qwen_index = 0
                        qwen_lst = []
                        for j in range(self.config.line_num_in_one_call):
                            if i + j >= len(text_lines):
                                break
                            
                            if qwen_index >= len(qwen_result_lst):
                                qwen_lst.append("AI翻译漏行")
                                print(f"补充了一个AI翻译漏行")
                                break
                            m = time_pattern.match(text_lines[i + j])
                            if m:
                                raw_time_str, raw_text = m.groups()
                            m = time_pattern.match(qwen_result_lst[qwen_index])
                            if m:
                                trans_time_str, trans_text = m.groups()
                            if raw_time_str == trans_time_str:
                                qwen_index += 1
                                qwen_lst.append(trans_text)
                            else:
                                qwen_lst.append("AI翻译漏行")
                        print("\n".join(qwen_lst))

                    translated_subtitles.extend(qwen_lst)
                    print(len(translated_subtitles))
            else:
                total_chara = 0
                subtitles = []
                for i in range(0, len(text_lines)):
                    subtitle = text_lines[i]
                    total_chara += len(subtitle)
                    subtitles.append(subtitle)
                    # 打包翻译，减少API调用次数
                    if total_chara > self.character_limit:
                        batch_translate(subtitles)
                        subtitles = []
                        total_chara = 0
                        time.sleep(.1)  # 等待0.1秒，防止被ban。

                batch_translate(subtitles)

        if self.config.translate_api == "qwen":
            API_USAGE_RECORDER.show()

        # 合并翻译结果
        for i in range(len(text_lines)):
            text_lines[i] = text_lines[i].strip() + r"@@@" + \
                translated_subtitles[i].strip() + "\n"

        return text_lines


if __name__ == '__main__':
    from time import time

