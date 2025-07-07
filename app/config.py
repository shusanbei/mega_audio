from environs import Env
import os
from dotenv import load_dotenv
from app.storage import MinIOStorage
from app.voice_processor import VoiceProcessor
from concurrent.futures import ThreadPoolExecutor

# 加载.env文件
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
env = Env()

# 全局线程池
executor = ThreadPoolExecutor(max_workers=2)

# 语音处理器实例缓存
_processors = {
    False: VoiceProcessor(stream=False),  # 非流式实例
    True: VoiceProcessor(stream=True)    # 流式实例
}

# 初始化MinIO客户端
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

def get_minio_client():
    """获取MinIO客户端实例"""
    return minio

def get_voice_processor(stream=False):
    """获取语音处理器实例
    Args:
        stream (bool): 是否获取流式处理器实例(默认为False)
    Returns:
        VoiceProcessor: 语音处理器实例
    """
    return _processors[stream]

def get_thread_pool():
    """获取线程池实例"""
    return executor
