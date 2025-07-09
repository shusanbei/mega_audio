# 构建阶段
FROM continuumio/miniconda3:latest AS builder

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
RUN conda create -y -n app_env python=3.10

# 配置 conda
RUN conda config --add channels defaults && \
    conda config --add channels conda-forge && \
    conda config --set channel_priority strict

# 正确安装 conda 包（使用主 conda 路径）
RUN /opt/conda/bin/conda install -y -n app_env -c conda-forge pynini=2.1.5

# 安装其他 pip 包
RUN /opt/conda/envs/app_env/bin/pip install --no-cache-dir -r requirements.txt

# 复制 whl 包到镜像
COPY ttsfrd_dependency-0.1-py3-none-any.whl .
COPY ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl .

# 安装这两个 whl 包（在 pip install requirements.txt 之后）
RUN /opt/conda/envs/app_env/bin/pip install --no-cache-dir ttsfrd_dependency-0.1-py3-none-any.whl \
    && /opt/conda/envs/app_env/bin/pip install --no-cache-dir ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl

# 运行阶段
FROM continuumio/miniconda3:latest

LABEL maintainer="purui7"
WORKDIR /app

# 复制整个conda安装和环境
COPY --from=builder /opt/conda /opt/conda
ENV PATH="/opt/conda/envs/app_env/bin:$PATH" \
    CONDA_DEFAULT_ENV=app_env \
    CONDA_PREFIX=/opt/conda/envs/app_env

# 安全配置
RUN useradd -m appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /opt/conda
USER appuser

# 初始化conda环境
RUN echo "source /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    conda init bash

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY --chown=appuser:appuser . /app/
EXPOSE 15012

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:15012 || exit 1

CMD ["/opt/conda/envs/app_env/bin/python", "-m", "flask", "--app", "main.py", "run", "--host=0.0.0.0", "--port=15012"]
