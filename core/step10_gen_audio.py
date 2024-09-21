import os, sys
import pandas as pd
from tqdm import tqdm
import soundfile as sf
import subprocess
from rich import print as rprint
from rich.panel import Panel
from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.all_tts_functions.gpt_sovits_tts import gpt_sovits_tts_for_videolingo
from core.all_tts_functions.openai_tts import openai_tts
from core.all_tts_functions.edge_tts import edge_tts
from core.all_tts_functions.azure_tts import azure_tts

console = Console()

def check_wav_duration(file_path):
    try:
        audio_info = sf.info(file_path)
        return audio_info.duration
    except Exception as e:
        raise Exception(f"Error checking duration: {str(e)}")

def parse_srt_time(time_str):
    hours, minutes, seconds = time_str.strip().split(':')
    seconds, milliseconds = seconds.split(',')
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000

def tts_main(text, save_as, number, task_df):
    from config import TTS_METHOD
    if TTS_METHOD == 'openai':
        openai_tts(text, save_as)
    elif TTS_METHOD == 'gpt_sovits':
        #! 注意 gpt_sovits_tts 只支持输出中文，输入中文或英文
        gpt_sovits_tts_for_videolingo(text, save_as, number, task_df)
    elif TTS_METHOD == 'edge_tts':
        (text, save_as)
    elif TTS_METHOD == 'azure_tts':
        azure_tts(text, save_as)

def generate_audio(text, target_duration, save_as, number, task_df):
    from config import MIN_SPEED_FACTOR, MAX_SPEED_FACTOR
    temp_filename = f"output/audio/tmp/{number}_temp.wav"

    tts_main(text, temp_filename, number, task_df)

    original_duration = check_wav_duration(temp_filename)
    speed_factor = original_duration / target_duration

    # Check speed factor and adjust audio speed
    if MIN_SPEED_FACTOR <= speed_factor <= MAX_SPEED_FACTOR:
        change_audio_speed(temp_filename, save_as, speed_factor)
        final_duration = check_wav_duration(save_as)
        rprint(f"✅ {number} Adjusted audio: {save_as} | Duration: {final_duration:.2f}s | Required: {target_duration:.2f}s | Speed factor: {speed_factor:.2f}")
    elif speed_factor < MIN_SPEED_FACTOR:
        change_audio_speed(temp_filename, save_as, MIN_SPEED_FACTOR)
        final_duration = check_wav_duration(save_as)
        rprint(f"⚠️ {number} Adjusted audio: {save_as} | Duration: {final_duration:.2f}s | Required: {target_duration:.2f}s | Speed factor: {MIN_SPEED_FACTOR}")
    else:  # speed_factor > MAX_SPEED_FACTOR
        rprint(f"⚠️ {number} Speed factor out of range: {speed_factor:.2f}, attempting to simplify subtitle...")
        
        punctuation = ',.!?;:，。！？；：'
        trimmed_text = ''.join([char if char not in punctuation else ' ' for char in text]).replace('  ', ' ')
        
        rprint(f"Original subtitle: {text} | Simplified subtitle: {trimmed_text}")
        
        tts_main(trimmed_text, temp_filename, number, task_df)
        new_original_duration = check_wav_duration(temp_filename)
        new_speed_factor = new_original_duration / target_duration

        change_audio_speed(temp_filename, save_as, new_speed_factor)
        final_duration = check_wav_duration(save_as)
        rprint(f"✅ {number} Adjusted audio: {save_as} | Duration: {final_duration:.2f}s | Required: {target_duration:.2f}s | Speed factor: {new_speed_factor:.2f}")

    if os.path.exists(temp_filename):
        os.remove(temp_filename)

def change_audio_speed(input_file, output_file, speed_factor):
    atempo = speed_factor
    cmd = ['ffmpeg', '-i', input_file, '-filter:a', f'atempo={atempo}', '-y', output_file]
    subprocess.run(cmd, check=True, stderr=subprocess.PIPE)

def process_sovits_tasks():
    # TODO 多线程，但是很容易文件冲突出错？
    tasks_df = pd.read_excel("output/audio/sovits_tasks.xlsx")
    error_tasks = []
    os.makedirs('output/audio/segs', exist_ok=True)

    with console.status("[bold green]处理任务中...") as status:
        for _, row in tqdm(tasks_df.iterrows(), total=len(tasks_df)):
            output_file = f'output/audio/segs/{row["number"]}.wav'
            if os.path.exists(output_file):
                rprint(f"[yellow]文件 {output_file} 已存在,跳过处理[/yellow]")
                continue
            try:
                generate_audio(row['text'], float(row['duration']), output_file, row['number'], tasks_df)
            except Exception as e:
                error_tasks.append(row['number'])
                rprint(Panel(f"任务 {row['number']} 处理出错: {str(e)}", title="错误", border_style="red"))

    if error_tasks:
        error_msg = f"以下任务处理出错: {', '.join(map(str, error_tasks))}"
        rprint(Panel(error_msg, title="处理失败的任务", border_style="red"))
        raise Exception()
    
    rprint(Panel("任务处理完成", title="成功", border_style="green"))

if __name__ == "__main__":
    process_sovits_tasks()