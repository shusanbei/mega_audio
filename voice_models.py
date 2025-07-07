from funasr import AutoModel
from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.utils.file_utils import load_wav
import torchaudio
import os
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify
import base64
from datetime import datetime
import torch
import gc
from concurrent.futures import ThreadPoolExecutor
import tempfile
import shutil
import requests
from minio import Minio
from minio.error import S3Error
from mimetypes import guess_type
from typing import Union, Optional
from environs import Env
from dotenv import load_dotenv
# 加载.env文件中的环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
env = Env()
app = Flask(__name__)
# 全局线程池
executor = ThreadPoolExecutor(max_workers=2)


class MinIOStorage:
    def __init__(self, endpoint: str = None, access_key: str = None, secret_key: str = None, secure: bool = True):
        """
        初始化 MinIO 客户端
        Args:
            endpoint: MinIO服务器地址(可选)
            access_key: 访问密钥(可选)
            secret_key: 密钥(可选)
            secure: 是否使用HTTPS
        """
        # 处理endpoint，移除协议和路径部分
        if endpoint:
            # 移除http://或https://前缀
            endpoint = endpoint.replace('http://', '').replace('https://', '')
            # 移除路径部分
            if '/' in endpoint:
                endpoint = endpoint.split('/')[0]
            # 确保包含端口号
            if ':' not in endpoint:
                endpoint += ':9000'  # MinIO默认端口
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )

    def upload_file(self,
                    bucket_name: str,
                    object_name: str,
                    file_path: Union[str, bytes, os.PathLike],
                    content_type: Optional[str] = None) -> bool:
        """
        上传文件到 MinIO

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（在桶中的路径）
            file_path: 要上传的文件路径
            content_type: 文件的MIME类型

        Returns:
            bool: 上传是否成功
        """
        try:
            # 确保bucket存在
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)

            # 上传文件
            self.client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type
            )
            return True

        except S3Error as e:
            print(f"上传文件失败: {e}")
            return False

    import os
    from mimetypes import guess_type
    from typing import Union, Optional

    def upload_audio_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: Union[str, bytes, os.PathLike],
            content_type: Optional[str] = None,
            verify_extension: bool = True  # 可选：检查文件扩展名是否为音频格式
    ) -> bool:
        """
        上传音频文件到 MinIO（支持自动识别MIME类型）

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（在桶中的路径）
            file_path: 要上传的音频文件路径（如 .wav, .mp3）
            content_type: 手动指定MIME类型（如未指定则自动识别）
            verify_extension: 是否检查文件扩展名为音频格式（默认True）

        Returns:
            bool: 上传是否成功
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"错误：文件不存在 {file_path}")
                return False

            # 可选：验证文件扩展名是否为常见音频格式
            if verify_extension:
                audio_extensions = {'.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a'}
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in audio_extensions:
                    print(f"警告：文件扩展名 {file_ext} 不是常见音频格式")

            # 自动识别MIME类型（如果未手动指定）
            if content_type is None:
                guessed_type, _ = guess_type(file_path)
                if guessed_type is None:
                    guessed_type = 'audio/wav' if file_ext == '.wav' else 'audio/mpeg'
                content_type = guessed_type

            # 确保存储桶存在
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)

            # 上传文件
            self.client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type
            )
            return True

        except S3Error as e:
            print(f"上传音频文件失败: {e}")
            return False

    def download_file(self,
                      bucket_name: str,
                      object_name: str,
                      file_path: str) -> bool:
        """
        从 MinIO 下载文件

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（在桶中的路径）
            file_path: 下载到本地的文件路径

        Returns:
            bool: 下载是否成功
        """
        try:
            self.client.fget_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=file_path
            )
            return True

        except S3Error as e:
            print(f"下载文件失败: {e}")
            return False

    def get_file_content(self,
                         bucket_name: str,
                         object_name: str) -> Optional[Union[bytes, str]]:
        """
        获取MinIO上文件的内容

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（在桶中的路径）

        Returns:
            Union[bytes, str]: 文件内容(自动解码为字符串)，如果出错则返回None
        """
        try:
            response = self.client.get_object(
                bucket_name=bucket_name,
                object_name=object_name
            )
            data = response.data
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return data

        except S3Error as e:
            print(f"获取文件失败: {e}")
            return None
        finally:
            if 'response' in locals():
                response.close()
                response.release_conn()

    def get_wav_file(self,
                     bucket_name: str,
                     object_name: str,
                     save_path: Optional[str] = None) -> Optional[Union[bytes, str]]:
        """
        从MinIO获取WAV音频文件内容，并可选择保存到本地

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（在桶中的路径）
            save_path: (可选) 本地保存路径，如未提供则返回二进制数据

        Returns:
            Optional[Union[bytes, str]]:
                - 如果 save_path=None，返回二进制数据（bytes）
                - 如果 save_path 是路径，返回保存状态字符串（"success" 或错误信息）
                - 出错时返回 None
        """
        try:
            response = self.client.get_object(
                bucket_name=bucket_name,
                object_name=object_name
            )
            data = response.data

            # 检查是否为WAV文件（可选）
            if not object_name.lower().endswith('.wav'):
                print("警告：文件扩展名不是.wav，但继续处理")

            # 如果提供了保存路径，写入本地文件
            if save_path:
                try:
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    return "success"
                except IOError as e:
                    return f"保存文件失败: {e}"
            else:
                return data  # 直接返回二进制数据

        except S3Error as e:
            print(f"获取WAV文件失败: {e}")
            return None
        finally:
            if 'response' in locals():
                response.close()
                response.release_conn()


class VoiceProcessor:
    def __init__(self, 
                 asr_model_dir: str = "pretrained_models/SenseVoiceSmall",
                 # tts_model_dir: str = "iic/CosyVoice2-0.5B",
                 tts_model_dir: str = "pretrained_models/CosyVoice2-0.5B",
                 prompt_audio_path: str = "./asset/zero_shot_prompt.wav",
                 stream: bool = False
                 ):
        """
        初始化语音处理器
        
        Args:
            asr_model_dir (str): SenseVoice模型目录
            tts_model_dir (str): CosyVoice模型目录
            prompt_audio_path (str): TTS提示音频路径
        """
        # 设置CUDA设备
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # 初始化ASR模型
        self.asr_model = AutoModel(
            model=asr_model_dir,
            trust_remote_code=True,
            # device=self.device
        )
        print(f"--使用设备: {self.device}--")
        
        # 初始化TTS模型
        self.tts_model = CosyVoice2(
            tts_model_dir, 
            load_jit=False,       # 使用JIT加速
            load_trt=False,       # 使用TensorRT加速
            fp16=True if torch.cuda.is_available() else False,           # 使用半精度
            use_flow_cache=True if stream else False   # 使用缓存
        )
        
        # 加载TTS提示音频
        self.prompt_speech = load_wav(prompt_audio_path, 16000)
        
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 设置模型为评估模式
        # self.tts_model.eval()
        
        # 启用CUDA优化
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True

    def __del__(self):
        """清理资源"""
        try:
            # 清理临时目录
            shutil.rmtree(self.temp_dir)
            # 清理GPU内存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # 强制垃圾回收
            gc.collect()
        except:
            pass

    def process_asr(self, audio_file_path: str) -> Dict[str, Any]:
        """
        处理语音识别
        
        Args:
            audio_file_path (str): 音频文件路径
            
        Returns:
            Dict[str, Any]: 包含识别结果的字典
        """
        try:
            # with torch.no_grad():  # 禁用梯度计算
            result = self.asr_model.generate(
                input=audio_file_path,
                cache={},
                language="auto",
                use_itn=False,
            )
            
            # 提取文本结果
            asr_text = result[0]['text'].split(">")[-1].strip()
            
            return {
                "success": True,
                "text": asr_text,
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "text": None,
                "error": str(e)
            }
        finally:
            # 清理内存
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def process_tts(self,
                    text: str,
                    audio_file_path_tts: Optional[str] = None,  # 修改为可选，默认None
                    output_path: Optional[str] = None,
                    reference_text: str = "希望你以后能够做的比我还好呦。",
                    stream: bool = False
                    ):
        """
        处理文本转语音
        
        Args:
            text (str): 要转换的文本
            audio_file_path_tts (Optional[str]): 音频文件路径，如果为None则使用默认音频
            output_path (Optional[str]): 输出文件路径，如果为None则自动生成
            reference_text (str): 参考文本
            stream (bool): 是否使用流式处理
            
        Returns:
            Dict[str, Any]: 包含处理结果的字典
        """
        if audio_file_path_tts is None:
            # 默认音频文件路径
            audio_file_path_tts = "asset/zero_shot_prompt.wav"
            # 检查文件是否存在，如果不存在，可以记录警告或报错
        if not os.path.exists(audio_file_path_tts):
            if stream:
                def error_stream():
                    yield base64.b64encode(f"默认音频文件不存在: {audio_file_path_tts}".encode('utf-8')).decode('utf-8')
                return error_stream
            else:
                return {
                    "success": False,
                    "error": f"默认音频文件不存在: {audio_file_path_tts}"
                }
        prompt_speech_16k = load_wav(audio_file_path_tts, 16000)
        assert self.tts_model.add_zero_shot_spk(reference_text, prompt_speech_16k, 'my_zero_shot_spk') is True
        if stream:
            import io
            def audio_stream():
                try:
                    with torch.no_grad():
                        for i, result in enumerate(self.tts_model.inference_cross_lingual(
                            text,
                            prompt_speech_16k,
                            stream=True
                        )):
                            buf = io.BytesIO()
                            torchaudio.save(buf, result['tts_speech'], 22050, format='wav')
                            buf.seek(0)
                            audio_chunk = buf.read()
                            audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                            yield audio_base64 + '\n'
                finally:
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
            return audio_stream
        else:
            try:
                if output_path is None:
                    output_path = os.path.join(self.temp_dir, f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
                with torch.no_grad():
                    for i, result in enumerate(self.tts_model.inference_cross_lingual(
                        text,
                        prompt_speech_16k,
                        stream=False
                    )):
                        torchaudio.save(output_path, result['tts_speech'], 22050)
                        break
                return {
                    "success": True,
                    "output_path": output_path,
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "output_path": None,
                    "error": str(e)
                }
            finally:
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

# 创建全局处理器实例
env = Env()
processor = VoiceProcessor()
# 直接使用项目根目录下的.env文件
env_file = ".env"

if os.path.exists(env_file):
    env.read_env(env_file)
else:
    raise FileNotFoundError("未找到.env配置文件")
# 使用传入参数或环境变量配置
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
    """
    try:
        # 初始化变量
        temp_path = None

        # 方式1：通过URL处理
        if 'audio_url' in request.form:
            file_url = request.form['audio_url']
            print(f"文件URL: {file_url}")
            try:
                response = requests.get(file_url, stream=True)
                response.raise_for_status()
                # 生成临时文件路径
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

        # 方式2：通过上传的文件处理（可选，如果需要同时支持上传文件）
        elif 'audio' in request.files:
            audio_file = request.files['audio']
            # 生成临时文件路径
            temp_path = os.path.join(processor.temp_dir, f"asr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
            audio_file.save(temp_path)
            print(f"文件已保存: {temp_path}")

        else:
            return jsonify({
                "success": False,
                "error": "未找到音频文件或音频URL"
            }), 400

        # 使用线程池处理ASR
        future = executor.submit(processor.process_asr, temp_path)
        result = future.result()

        # 删除临时文件
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
    """
    try:
        # 1. 获取参数
        text = request.form.get('text')
        audio_url = request.form.get('audio_url')  # 改为audio_url更明确
        reference_text = request.form.get('reference_text', "希望你以后能够做的比我还好呦。")
        stream = request.form.get('stream', 'false').lower() == 'true'

        if not text:
            return jsonify({"success": False, "error": "未提供文本"}), 400

        # 2. 初始化音频路径
        DEFAULT_AUDIO = "asset/zero_shot_prompt.wav"  # 默认音频路径
        temp_path = DEFAULT_AUDIO  # 初始化为默认值

        # 3. 处理音频URL（如果提供）
        if audio_url:
            print(f"文件URL: {audio_url}")
            try:
                response = requests.get(audio_url, stream=True)
                response.raise_for_status()

                # 生成临时文件路径
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

        # 3. 保存临时音频文件
        # temp_audio_path = os.path.join(processor.temp_dir, f"tts_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
        # audio_file.save(temp_audio_path)

        # 4. 处理TTS
        if stream:
            processor = VoiceProcessor(stream=stream)
            # 使用流式处理
            audio_stream = processor.process_tts(text, temp_path, None, reference_text, stream)
            # 删除临时音频（仅当不是默认音频时）
            if temp_path != DEFAULT_AUDIO:
                try:
                    os.remove(temp_path)
                    print(f"已删除临时文件: {temp_path}")
                except Exception as e:
                    print(f"删除临时文件失败: {e}")
            from flask import Response
            return Response(audio_stream(), mimetype='text/plain')
        else:
            future = executor.submit(processor.process_tts, text, temp_path, None, reference_text, stream)
            result = future.result()

            # 5. 删除临时音频（仅当不是默认音频时）
            if temp_path != DEFAULT_AUDIO:
                try:
                    os.remove(temp_path)
                    print(f"已删除临时文件: {temp_path}")
                except Exception as e:
                    print(f"删除临时文件失败: {e}")

            if result["success"]:
                # 读取音频并转base64
                with open(result["output_path"], 'rb') as audio_file:
                    audio_data = audio_file.read()
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                    file = minio.upload_file(
                        bucket_name='cool',
                        object_name='27/temp1.wav',
                        file_path=result["output_path"],
                        content_type='wav'
                    )
                    print(file)

                # 保存到本地 output 目录
                import os
                from datetime import datetime
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
                return jsonify({"success": True, "audio_base64": audio_base64, "error": None})
            else:
                print(f"TTS处理失败: {result}")
                return jsonify(result), 500

    except Exception as e:
        print(f"TTS接口异常: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def main():
    # 启动Flask服务
    app.run(host='0.0.0.0', port=15012, debug=False, threaded=True)

if __name__ == "__main__":
    main()