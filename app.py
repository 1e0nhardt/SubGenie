import time

import tyro

from src.sub_genie import SubGenie, SubGenieConfig

if __name__ == '__main__':
    start_t = time.time()
    config = tyro.cli(SubGenieConfig)
    generator = SubGenie(config)
    if config.task == 'download':
        generator.download_video()
    elif config.task == 'generate':
        generator.batch_generate()
    elif config.task == 'continue':
        generator.continue_generate()
    else:
        print(f"不支持的任务类型:{config.task}")
        exit()
    print(f"总耗时: {time.time() - start_t}")
