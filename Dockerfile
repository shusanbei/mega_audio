# FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime
FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# RUN sed -i s@/archive.ubuntu.com/@/mirrors.aliyun.com/@g /etc/apt/sources.list
RUN apt-get update -y
RUN apt-get -y install unzip g++ ffmpeg
# RUN git lfs install
# RUN git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
# # here we use python==3.10 because we cannot find an image which have both python3.8 and torch2.0.1-cu118 installed
# RUN cd CosyVoice && pip3 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com
# RUN cd CosyVoice/runtime/python/grpc && python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. cosyvoice.proto

COPY . /app/
RUN pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# RUN pip3 install --no-cache-dir ttsfrd_dependency-0.1-py3-none-any.whl
# RUN pip3 install --no-cache-dir ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl
RUN pip3 install matcha-tts -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip3 install peft -i https://pypi.tuna.tsinghua.edu.cn/simple

# 暴露端口
EXPOSE 15012

# 启动命令
CMD ["python", "-m", "flask", "--app", "main.py", "run", "--host=0.0.0.0", "--port=15012"]