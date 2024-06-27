@echo off
SETLOCAL

:: Activate the virtual environment
CALL sub_genie\Scripts\activate

:: 默认配置，使用qwen-turbo翻译
python app.py

:: 使用通义千问qwen-max翻译(效果最好)
::python app.py --translator.translate-api qwen --translator.qwen-model qwen-max --translator.line-num-in-one-call 42

:: 下载视频和封面
::python app.py --task download --youtube-downloader.url "https://www.youtube.com/watch?v=ulgh_neTJG8&list=PL6SABXRSlpH8CD71L7zye311cp9R4JazJ"

:: 手动用ChatGPT或Kimi翻译
:: python app.py --skip-translate
:: 将翻译结果复制到xx_zh.list后，合并两个文件并生成ass双语字幕。
::python app.py --task continue

pause
ENDLOCAL