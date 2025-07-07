# Mega Audio 语音处理服务

## 项目简介

本项目是一个模块化的语音处理服务，基于Flask框架，提供：
- 语音识别(ASR) - 使用SenseVoiceSmall模型
- 文本转语音(TTS) - 使用CosyVoice2模型
- 流式音频处理
- MinIO对象存储集成

## 主要特性

- 🚀 **模块化架构**：清晰分离业务逻辑、模型处理、存储等模块
- ⚡ **高性能**：支持CUDA加速和流式处理
- 🔒 **安全存储**：自动上传音频到MinIO
- 📦 **容器化支持**：提供Dockerfile和docker-compose配置

## 项目结构

```
mega_audio/
├── app/                   # 核心应用模块
│   ├── __init__.py
│   ├── api.py            # API路由
│   ├── config.py         # 配置管理
│   ├── storage.py        # MinIO存储
│   └── voice_processor.py # ASR/TTS处理器
├── asset/                # 资源文件
├── output/               # 输出目录
├── pretrained_models/    # 模型文件
├── cosyvoice/            # CosyVoice代码
├── main.py               # 主入口
├── model_download.py     # 模型下载脚本
├── requirements.txt      # 依赖
└── README.md
```

## 快速开始

### 环境准备

1. 安装Python 3.11
2. 安装依赖：
```bash
pip install -r requirements.txt
```

### 配置

复制.env.example并配置：
```ini
# MinIO配置
MINIO_ADDRESS=your_minio_server
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key 
MINIO_SECURE=False

# 模型路径(可选)
ASR_MODEL_DIR=pretrained_models/SenseVoiceSmall
TTS_MODEL_DIR=pretrained_models/CosyVoice2-0.5B
```

### 启动服务

```bash
python main.py
```

## API文档

### 语音识别接口
`POST /process_asr`

参数：
- `audio_url`: 音频URL (可选)
- `audio`: 上传的音频文件 (可选)

响应：
```json
{
  "success": bool,
  "text": "识别结果",
  "error": "错误信息"
}
```

### 文本转语音接口  
`POST /process_tts`

参数：
- `text`: 要合成的文本 (必填)
- `audio_url`: 参考音频URL (可选)
- `reference_text`: 参考文本 (默认值)
- `stream`: 是否流式输出 (true/false)

响应：
- 非流式：返回base64编码的音频
- 流式：返回分块的base64音频流

## 开发指南

### 模型下载（CosyVoice2-0.5B）

```bash
python model_download.py
```

### Docker部署

```bash
docker-compose up -d
```

## 参考
- [CosyVoice2 官方文档](https://github.com/alibaba-damo-academy/CosyVoice)
- [MinIO 官方文档](https://min.io/)

---
如有问题请联系[项目维护者](1710886795@qq.com)。
