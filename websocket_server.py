import asyncio
import json
import re
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import websockets
from rich.pretty import pprint

from src.sub_genie import SubGenie, SubGenieConfig
from src.translator import Translator
from src.utils import CONSOLE, SAMPLE_RATE, qwen_call_once, qwen_translate
from src.whisper_asr import WhisperAsr, WhisperAsrConfig

# test_audio_path = "assets/audio/test.m4a"
whisper_asr_config = WhisperAsrConfig()
whisper_asr_instance = WhisperAsr(whisper_asr_config)

def run_asr(payload):
    try:
        global whisper_asr_instance

        if Path(payload["audio_path"]).exists():
            whisper_asr_instance.load_audio(payload["audio_path"])
            slice_start, slice_end = [float(t.strip()) for t in payload["time_range"].split(",")]
            ret = whisper_asr_instance.transcribe_audio_slice(slice_start, slice_end)
        else:
            print("Audio file not found")
            ret = "[]"
        return ret
    except Exception:
        traceback.print_exc()
        return "[]"


def run_qwen_translate(payload):
    try:
        pattern = re.compile(r"\[\d+\.\d+->\d+\.\d+\]")
        qwen_result = qwen_translate(payload)
        qwen_lst = re.split(pattern, qwen_result)[1:]
        return qwen_lst
    except Exception:
        traceback.print_exc()


def run_qwen_call_once(payload):
    try:
        qwen_result = qwen_call_once(payload)
        return qwen_result
    except Exception:
        traceback.print_exc()


def default_handler(payload):
    print("##########Using Default Task Handler!!!!!!!!!#############")
    print(payload)
    print("##########Using Default Task Handler End!!!!!#############")


TASK_HANDLER_MAP = {
    "asr": run_asr,
    "qwen_translate": run_qwen_translate,
    "qwen_call_once": run_qwen_call_once,
}


async def run_task(ws, task_dict):
    await ws.send(json.dumps({
        "type": task_dict["type"],
        "task_id": task_dict["task_id"],
        "task_progress": 0
    }))

    CONSOLE.print(f"[green]Task: {task_dict['type']} {task_dict['task_id']} start!")
    ret = TASK_HANDLER_MAP.get(task_dict["type"], default_handler)(task_dict["payload"])
    CONSOLE.print(f"[green]Task: {task_dict['type']} {task_dict['task_id']} done!")
    
    await ws.send(json.dumps({
        "type": task_dict["type"],
        "task_id": task_dict["task_id"],
        "task_progress": 100,
        "data": ret 
    }))


async def server(ws):
    async for msg in ws:
        CONSOLE.rule("Msg from client", style="bold blue")
        # 防止路径问题, '\\' 如果被当参数传两次，第一次会正确解析，第二次就会出错
        msg_dict = json.loads(msg.replace("\\\\", "/"))
        CONSOLE.print("Msg from client")
        pprint(msg_dict)
        CONSOLE.rule(style="bold blue")

        try:
            if msg_dict["type"] in TASK_HANDLER_MAP.keys():
                CONSOLE.print(f"[green]Create Task: {msg_dict['type']} {msg_dict['task_id']}")
                await run_task(ws, msg_dict)
            else:
                print("Invalid task data %s" % msg_dict)
        except Exception as e:
            traceback.print_exc()
            await ws.send(json.dumps({
                "type": "error",
                "task_id": msg_dict["task_id"],
                "data": str(e),
            }))


async def main():
    async with websockets.serve(server, "localhost", 5000, max_size = 5*1024*1024):
        await asyncio.Future()  # run forever


if __name__ == '__main__':
    CONSOLE.rule()
    CONSOLE.rule("启动！")
    CONSOLE.rule()
    asyncio.run(main())