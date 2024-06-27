# SubGenie

## 目录
- [SubGenie](#SubGenie)
- [目录](#目录)
- [简介](#简介)
- [安装与使用指南](#安装与使用指南)
- [视频教程](#视频教程)
- [贡献指南](#贡献指南)

## 简介
SubGenie是一个开源工具，整合了YouTube视频下载，Whisper语音识别，字幕翻译等功能，主要用于为视频生成高质量双语字幕。

SubGenie字幕生成工具使用faster-whisper库进行语音识别，对识别结果进行基于简单规则的断句，并使用deepmultilingualpunctuation库修正长视频识别结果中没有标点符号的情况。再调用通义千问的API使用qwen-max模型进行翻译。最终生成ass格式的双语字幕。

此外，我使用[Godot 4.2.2 stable](https://github.com/godotengine/godot)，基于[GoZen_lite](https://github.com/VoylinsGamedevJourney/GoZen_lite)，写了一个[字幕编辑界面]()，方便对字幕进行校正，以进一步提升字幕质量。

## 安装与使用指南
1. **克隆仓库**：
    ```bash
    git clone https://github.com/1e0nhardt/SubGenie
    ```
2. **安装虚拟环境**：
    进入 `SubGenie` 目录并双击运行setup_windows.bat 脚本：
    ```bash
    cd SubGenie
    setup_windows.bat
    ```
    默认安装为 cu121 版本的 PyTorch 如果你需要手动安装特定 CUDA 版本的 PyTorch，可以去`setup_windows.bat`中修改。
3. **环境设置**：
    在运行程序之前，需要进行以下环境设置：  
    **模型下载**
    - 自己动手，丰衣足食。
        - Whisper模型(medium, large-v3等)
        - deepmultilingualpunctuation模型(oliverguhr/fullstop-punctuation-multilang-large)
    - 以下为推荐配置。
        - Whisper-largev3
        - oliverguhr-fullstop-punctuation-multilang-large
    - [百度网盘](https://pan.baidu.com/s/1q6Y0zZzVfJZfZVZq-X0Nlw)
    - [夸克网盘](https://pan.quark.cn/s/dc2d2a747d6b)

    **设置通义千问API key**
    - 在系统环境变量中添加`DASHSCOPE_API_KEY=your_api_key`
    - 或者直接填入`src/utils.py`的第44行

    **安装ffmpeg**
    - 下载ffmpeg，并配置好环境变量。
4. **运行程序**：
    - 运行`start_py_venv.bat`启动虚拟环境。
    - 在虚拟环境中，输入`python app.py -h`查看帮助。
    - 常用命令示例见`run_sub_genie.bat`。
5. **人工修正字幕**：
    - 打开websocket服务器 `start_server.bat`
    - 启动字幕编辑程序。

## 视频教程
[TODO]()

## 贡献指南
欢迎对 `SubGenie` 进行贡献。您可以通过 GitHub Issue 或 Pull Request 提交改进建议或报告问题。
