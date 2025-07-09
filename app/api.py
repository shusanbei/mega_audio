from flask import Flask, request, jsonify, Response
from app.config import get_voice_processor
from app.voice_processor import VoiceProcessor
from app.storage import MinIOStorage
from environs import Env
import os
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor
import base64

# 初始化Flask应用
app = Flask(__name__)

# 全局线程池
executor = ThreadPoolExecutor(max_workers=2)

# 初始化语音处理器
processor = get_voice_processor()

# 初始化MinIO客户端
env = Env()
env.read_env(".env")
endpoint = env.str('MINIO_ADDRESS')
access_key = env.str('MINIO_ACCESS_KEY')
secret_key = env.str('MINIO_SECRET_KEY')
secure = env.bool('MINIO_SECURE', False)
minio = MinIOStorage(
    endpoint=endpoint,
    access_key=access_key,
    secret_key=secret_key,
    secure=secure
)

@app.route('/process_asr', methods=['POST'])
def asr_endpoint():
    """
    ASR处理接口
    接收音频文件或音频URL，返回识别结果

    参数：
    - audio_url: 音频文件的URL（可选）

    """
    try:
        temp_path = None

        if 'audio_url' in request.form:
            file_url = request.form['audio_url']
            print(f"文件URL: {file_url}")
            try:
                response = requests.get(file_url, stream=True)
                response.raise_for_status()
                temp_path = os.path.join(processor.temp_dir, f"asr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"文件已下载: {temp_path}")
            except requests.exceptions.RequestException as e:
                return jsonify({
                    "success": False,
                    "error": f"下载失败: {e}"
                }), 400

        elif 'audio' in request.files:
            audio_file = request.files['audio']
            temp_path = os.path.join(processor.temp_dir, f"asr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
            audio_file.save(temp_path)
            print(f"文件已保存: {temp_path}")

        else:
            return jsonify({
                "success": False,
                "error": "未找到音频文件或音频URL"
            }), 400

        future = executor.submit(processor.process_asr, temp_path)
        result = future.result()

        try:
            os.remove(temp_path)
            print(f"删除临时文件: {temp_path}")
        except Exception as e:
            print(f"删除临时文件失败: {e}")

        return jsonify(result)

    except Exception as e:
        print(f"ASR接口异常: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/process_tts', methods=['POST'])
def tts_endpoint():
    """
    TTS处理接口
    接收文本和音频文件或音频URL，返回合成的音频

    参数：
    - text: 要合成的文本
    - audio_url: 可选的音频文件URL，用于参考音频
    - reference_text: 可选的参考文本，用于零-shot语音合成
    - stream: 是否使用流式处理（默认为false）

    """
    try:
        text = request.form.get('text')
        audio_url = request.form.get('audio_url')
        reference_text = request.form.get('reference_text', "希望你以后能够做的比我还好呦。")
        stream = request.form.get('stream', 'false').lower() == 'true'

        if not text:
            return jsonify({"success": False, "error": "未提供文本"}), 400

        DEFAULT_AUDIO = "asset/zero_shot_prompt.wav"
        temp_path = DEFAULT_AUDIO

        if audio_url:
            print(f"文件URL: {audio_url}")
            try:
                response = requests.get(audio_url, stream=True)
                response.raise_for_status()
                temp_path = os.path.join(
                    processor.temp_dir,
                    f"tts_ref_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                )
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"文件已下载: {temp_path}")
            except requests.exceptions.RequestException as e:
                return jsonify({
                    "success": False,
                    "error": f"下载失败: {e}"
                }), 400
        else:
            print(f"使用默认音频: {DEFAULT_AUDIO}")

        if stream:
            processor = get_voice_processor(stream=True)
            audio_stream = processor.process_tts(text, temp_path, None, reference_text, stream)
            if temp_path != DEFAULT_AUDIO:
                try:
                    os.remove(temp_path)
                    print(f"已删除临时文件: {temp_path}")
                except Exception as e:
                    print(f"删除临时文件失败: {e}")
            return Response(audio_stream(), mimetype='text/plain')
        else:
            # 使用默认的非流式处理器实例
            processor = get_voice_processor()
            future = executor.submit(processor.process_tts, text, temp_path, None, reference_text, stream)
            result = future.result()

            if temp_path != DEFAULT_AUDIO:
                try:
                    os.remove(temp_path)
                    print(f"已删除临时文件: {temp_path}")
                except Exception as e:
                    print(f"删除临时文件失败: {e}")

            if result["success"]:
                with open(result["output_path"], 'rb') as audio_file:
                    audio_data = audio_file.read()
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    minio_path = f"{endpoint}/cool/27/temp1.wav"
                    file = minio.upload_file(
                        bucket_name='cool',
                        object_name='27/temp1.wav',
                        file_path=result["output_path"],
                        content_type='wav'
                    )
                    print(minio_path)

                output_dir = 'output'
                os.makedirs(output_dir, exist_ok=True)
                save_name = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                save_path = os.path.join(output_dir, save_name)
                with open(save_path, 'wb') as f:
                    f.write(audio_data)
                print(f"音频已保存到本地: {save_path}")

                try:
                    os.remove(result["output_path"])
                except Exception as e:
                    print(f"删除TTS输出文件失败: {e}")
                return jsonify({
                    "success": True, 
                    "audio_base64": audio_base64,
                    "minio_path": minio_path,
                    "error": None
                })
            else:
                print(f"TTS处理失败: {result}")
                return jsonify(result), 500

    except Exception as e:
        print(f"TTS接口异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
