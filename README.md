# Mega Audio 项目说明

## 项目简介

本项目是一个基于 Flask 的语音处理服务，集成了 ASR（自动语音识别）、TTS（文本转语音）、MinIO 文件存储等功能，支持 CosyVoice2 语音合成模型，支持流式和非流式 TTS 输出。

## 主要功能
- 语音识别（ASR）：支持音频文件/URL识别为文本
- 文本转语音（TTS）：支持普通和流式输出，支持自定义参考音频
- MinIO 对象存储：音频文件自动上传到 MinIO
- 支持模型量化（PyTorch 动态量化/FP16）

## 依赖环境
- Python 3.8+
- Flask
- torch
- torchaudio
- funasr
- minio
- requests
- environs
- python-dotenv

安装依赖：
```bash
pip install -r requirements.txt
```

## 快速启动
1. 配置 .env 文件，填写 MinIO 相关参数：
   ```ini
   MINIO_ADDRESS=your_address
   MINIO_ACCESS_KEY=your_access_key
   MINIO_SECRET_KEY=your_secret_key
   MINIO_SECURE=False
   ```
2. 启动服务：
   ```bash
   python voice_models.py
   ```

## API 用法

### 1. 语音识别接口
- 路径：`/process_asr`
- 方法：POST
- 参数：
  - `audio_url`（可选）：音频文件URL
  - `audio`（可选）：上传音频文件
- 返回：JSON，包含识别文本

### 2. 文本转语音接口
- 路径：`/process_tts`
- 方法：POST
- 参数：
  - `text`（必填）：要合成的文本
  - `audio_url`（可选）：参考音频URL
  - `reference_text`（可选）：参考文本
  - `stream`（可选）：true/false，是否流式输出
- 返回：
  - 非流式：JSON，包含 base64 音频
  - 流式：HTTP 分块文本流，每块为 base64 音频片段

### 3. MinIO 文件上传
- 合成音频会自动上传到 MinIO 指定 bucket

## 目录结构
```
├── voice_models.py         # 主服务入口
├── requirements.txt        # 依赖包
├── Dockerfile / docker-compose.yml
├── asset/                  # 资源文件
├── output/                 # 输出音频
├── pretrained_models/      # 预训练模型（含 CosyVoice2-0.5B）
└── cosyvoice/              # CosyVoice 相关代码
```

## 参考
- [CosyVoice2 官方文档](https://github.com/alibaba-damo-academy/CosyVoice)
- [MinIO 官方文档](https://min.io/)

---
如有问题请联系[项目维护者](1710886795@qq.com)。
