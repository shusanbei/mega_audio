# 构建阶段
FROM python:3.11.11-slim-bookworm AS builder

# 设置工作目录
WORKDIR /build

# 复制依赖文件
COPY requirements.txt .
COPY ttsfrd_dependency-0.1-py3-none-any.whl .
COPY ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl .

# 更换APT源为清华镜像
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security/ bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 配置pip镜像源（阿里云PyPI通常稳定）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com

# 安装构建阶段必需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ python3-dev build-essential git \
    ffmpeg unzip sox libsox-dev wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装Miniforge
RUN wget --quiet https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh -O /tmp/miniforge.sh && \
    /bin/bash /tmp/miniforge.sh -b -p /opt/conda && \
    rm /tmp/miniforge.sh && \
    # 清理conda缓存
    /opt/conda/bin/conda clean -afy

# 配置Conda环境变量
ENV PATH="/opt/conda/bin:$PATH"

# 创建并激活Conda环境
RUN conda create -y -n app_env python=3.10 && \
    conda config --add channels defaults && \
    conda config --add channels conda-forge && \
    conda config --set channel_priority strict

# 安装Conda管理的依赖（pynini需要Conda环境）
RUN /opt/conda/bin/conda install -y -n app_env -c conda-forge pynini=2.1.5 && \
    /opt/conda/bin/conda clean -afy

# 安装Python依赖（使用环境内的pip）
RUN /opt/conda/envs/app_env/bin/pip install --upgrade pip
RUN /opt/conda/envs/app_env/bin/pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# RUN /opt/conda/envs/app_env/bin/pip install --no-cache-dir ttsfrd_dependency-0.1-py3-none-any.whl
# RUN /opt/conda/envs/app_env/bin/pip install --no-cache-dir ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl
RUN /opt/conda/envs/app_env/bin/pip install matcha-tts -i https://pypi.tuna.tsinghua.edu.cn/simple
# RUN /opt/conda/envs/app_env/bin/pip install onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple

# 运行阶段
FROM python:3.11.11-slim-bookworm

LABEL maintainer="purui7"
WORKDIR /app

RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security/ bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装运行时必需的系统依赖（Conda环境依赖的底层库）
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 libstdc++6 libsox3 ffmpeg curl sox libsox-dev && \ 
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制conda环境
COPY --from=builder /opt/conda/envs/app_env /opt/conda/envs/app_env

# 配置环境变量
ENV PATH="/opt/conda/envs/app_env/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# 复制应用代码
COPY . /app/

# 暴露端口
EXPOSE 15012

# 启动命令
CMD ["python", "-m", "flask", "--app", "main.py", "run", "--host=0.0.0.0", "--port=15012"]