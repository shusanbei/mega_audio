# 构建阶段
FROM python:3.11.11-slim-bookworm AS builder

# 设置工作目录
WORKDIR /build

# 首先复制 requirements.txt
COPY requirements.txt .

# 配置 apt 镜像源
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main non-free contrib" > /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main non-free contrib" >> /etc/apt/sources.list \
    && echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main non-free contrib" >> /etc/apt/sources.list

# 配置 pip 镜像源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

# 安装构建依赖并清理
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ python3-dev build-essential git ffmpeg unzip sox libsox-dev wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 Miniforge
RUN wget --quiet https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -O ~/miniforge.sh \
    && /bin/bash ~/miniforge.sh -b -p /opt/conda \
    && rm ~/miniforge.sh \
    && ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh \
    && echo "source /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc

ENV PATH="/opt/conda/bin:$PATH"

# 创建 Conda 环境并安装依赖
# 1. 创建基础环境
# 创建 Conda 环境
# 创建 Conda 环境
RUN conda create -y -n app_env python=3.10

# 配置 conda
RUN conda config --add channels defaults && \
    conda config --add channels conda-forge && \
    conda config --set channel_priority strict

# 正确安装 conda 包（使用主 conda 路径）
RUN /opt/conda/bin/conda install -y -n app_env -c conda-forge pynini=2.1.5

# 安装其他 pip 包
RUN /opt/conda/envs/app_env/bin/pip install --no-cache-dir -r requirements.txt

# 运行阶段
FROM python:3.11.11-slim-bookworm

LABEL maintainer="purui7"
WORKDIR /app

# 直接复制固定名称的 Conda 环境
COPY --from=builder /opt/conda/envs/app_env /opt/conda/envs/app_env
ENV PATH="/opt/conda/envs/app_env/bin:$PATH"

# 安全配置
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY . /app/
EXPOSE 15012

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; exit(0 if requests.get('http://localhost:15012').ok else 1)"

CMD ["/opt/conda/envs/app_env/bin/python", "-m", "flask", "--app", "app/api.py", "run", "--host=0.0.0.0", "--port=15012"]