from funasr import AutoModel
from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.utils.file_utils import load_wav
import torchaudio
import os
import subprocess
import sys
from typing import Optional, Dict, Any, Union
import base64
from datetime import datetime
import torch
import gc
import tempfile
import shutil

def download_model(model_type: str):
    """下载指定类型的模型"""
    try:
        print(f"正在下载{model_type}模型...")
        cmd = [sys.executable, "model_download.py"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"模型下载失败: {stderr.decode('utf-8')}")
        print(f"{model_type}模型下载完成")
    except Exception as e:
        print(f"模型下载过程中出错: {str(e)}")
        raise

class VoiceASR:
    def __init__(self, asr_model_dir: str = "pretrained_models/SenseVoiceSmall"):
        """
        初始化语音识别模型
        
        Args:
            asr_model_dir (str): ASR模型目录
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"正在加载ASR模型: {asr_model_dir}")
        try:
            if not os.path.exists(asr_model_dir):
                print("ASR模型不存在，尝试自动下载...")
                download_model("SenseVoiceSmall")
                if not os.path.exists(asr_model_dir):
                    raise FileNotFoundError(f"ASR模型目录不存在且下载失败: {asr_model_dir}")
            
            self.asr_model = AutoModel(
                model=asr_model_dir,
                trust_remote_code=True,
                disable_update=True
            )
            print("ASR模型加载完成")
        except Exception as e:
            print(f"ASR模型加载失败: {str(e)}")
            raise

    def process(self, audio_file_path: str) -> Dict[str, Any]:
        """
        处理语音识别
        
        Args:
            audio_file_path (str): 音频文件路径
            
        Returns:
            Dict[str, Any]: 包含识别结果的字典
        """
        try:
            result = self.asr_model.generate(
                input=audio_file_path, # 输入音频文件路径
                cache={},              # 缓存字典
                language="auto",       # 自动检测语言
                use_itn=False,         # 是否使用ITN（Inverse Text Normalization）
            )
            
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
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

class VoiceTTS:
    def __init__(self, 
                tts_model_dir: str = "pretrained_models/CosyVoice2-0.5B",
                prompt_audio_path: str = "./asset/zero_shot_prompt.wav",
                stream: bool = False):
        """
        初始化语音合成模型
        
        Args:
            tts_model_dir (str): TTS模型目录
            prompt_audio_path (str): 提示音频路径
            stream (bool): 是否使用流式处理
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"正在加载TTS模型: {tts_model_dir}")
        try:
            if not os.path.exists(tts_model_dir):
                print("TTS模型不存在，尝试自动下载...")
                download_model("CosyVoice2-0.5B")
                if not os.path.exists(tts_model_dir):
                    raise FileNotFoundError(f"TTS模型目录不存在且下载失败: {tts_model_dir}")
            
            self.tts_model = CosyVoice2(
                tts_model_dir, 
                load_jit=False,
                load_trt=False,
                fp16=True if torch.cuda.is_available() else False,
                use_flow_cache=True if stream else False
            )
            print("TTS模型加载完成")
        except Exception as e:
            print(f"TTS模型加载失败: {str(e)}")
            raise
        
        self.prompt_speech = load_wav(prompt_audio_path, 16000)
        self.stream = stream

    def process(self,
                text: str,
                audio_file_path_tts: Optional[str] = None,
                output_path: Optional[str] = None,
                reference_text: str = "希望你以后能够做的比我还好呦。") -> Union[Dict[str, Any], callable]:
        """
        处理文本转语音
        
        Args:
            text (str): 要转换的文本
            audio_file_path_tts (Optional[str]): 音频文件路径
            output_path (Optional[str]): 输出文件路径
            reference_text (str): 参考文本
            
        Returns:
            Union[Dict[str, Any], callable]: 返回结果字典或流式生成器
        """
        if audio_file_path_tts is None:
            audio_file_path_tts = "asset/zero_shot_prompt.wav"
            
        if not os.path.exists(audio_file_path_tts):
            if self.stream:
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
        
        if self.stream:
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
                    output_path = os.path.join(tempfile.mkdtemp(), f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
                    
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

class VoiceProcessor:
    def __init__(self, 
                 asr_model_dir: str = "pretrained_models/SenseVoiceSmall",
                 tts_model_dir: str = "pretrained_models/CosyVoice2-0.5B",
                 prompt_audio_path: str = "./asset/zero_shot_prompt.wav",
                 stream: bool = False):
        """
        初始化语音处理器
        
        Args:
            asr_model_dir (str): SenseVoice模型目录
            tts_model_dir (str): CosyVoice模型目录
            prompt_audio_path (str): TTS提示音频路径
            stream (bool): 是否使用流式处理
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.asr = VoiceASR(asr_model_dir)
        self.tts = VoiceTTS(tts_model_dir, prompt_audio_path, stream)
        self.temp_dir = tempfile.mkdtemp()
        
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True

    def __del__(self):
        """清理资源"""
        try:
            shutil.rmtree(self.temp_dir)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
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
        return self.asr.process(audio_file_path)

    def process_tts(self,
                    text: str,
                    audio_file_path_tts: Optional[str] = None,
                    output_path: Optional[str] = None,
                    reference_text: str = "希望你以后能够做的比我还好呦。",
                    stream: bool = False):
        """
        处理文本转语音
        
        Args:
            text (str): 要转换的文本
            audio_file_path_tts (Optional[str]): 音频文件路径
            output_path (Optional[str]): 输出文件路径
            reference_text (str): 参考文本
            stream (bool): 是否使用流式处理
            
        Returns:
            Dict[str, Any]: 包含处理结果的字典
        """
        if output_path is None:
            output_path = os.path.join(self.temp_dir, f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
        return self.tts.process(text, audio_file_path_tts, output_path, reference_text)
