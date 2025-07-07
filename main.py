from app.api import app
from app.config import get_voice_processor, get_minio_client, get_thread_pool

if __name__ == "__main__":
    # 初始化全局实例
    processor = get_voice_processor()
    minio = get_minio_client()
    executor = get_thread_pool()
    
    # 启动Flask服务
    app.run(host='0.0.0.0', port=15012, debug=False, threaded=True)
