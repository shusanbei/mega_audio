from minio import Minio
from minio.error import S3Error
import os
from mimetypes import guess_type
from typing import Union, Optional

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
        if endpoint:
            endpoint = endpoint.replace('http://', '').replace('https://', '')
            if '/' in endpoint:
                endpoint = endpoint.split('/')[0]
            if ':' not in endpoint:
                endpoint += ':9000'
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )

    def upload_file(self, bucket_name: str, object_name: str, file_path: Union[str, bytes, os.PathLike], 
                   content_type: Optional[str] = None) -> bool:
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)

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

    def upload_audio_file(self, bucket_name: str, object_name: str, file_path: Union[str, bytes, os.PathLike],
                         content_type: Optional[str] = None, verify_extension: bool = True) -> bool:
        try:
            if not os.path.exists(file_path):
                print(f"错误：文件不存在 {file_path}")
                return False

            if verify_extension:
                audio_extensions = {'.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a'}
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in audio_extensions:
                    print(f"警告：文件扩展名 {file_ext} 不是常见音频格式")

            if content_type is None:
                guessed_type, _ = guess_type(file_path)
                if guessed_type is None:
                    guessed_type = 'audio/wav' if file_ext == '.wav' else 'audio/mpeg'
                content_type = guessed_type

            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)

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

    def download_file(self, bucket_name: str, object_name: str, file_path: str) -> bool:
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

    def get_file_content(self, bucket_name: str, object_name: str) -> Optional[Union[bytes, str]]:
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

    def get_wav_file(self, bucket_name: str, object_name: str, save_path: Optional[str] = None) -> Optional[Union[bytes, str]]:
        try:
            response = self.client.get_object(
                bucket_name=bucket_name,
                object_name=object_name
            )
            data = response.data

            if not object_name.lower().endswith('.wav'):
                print("警告：文件扩展名不是.wav，但继续处理")

            if save_path:
                try:
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    return "success"
                except IOError as e:
                    return f"保存文件失败: {e}"
            else:
                return data
        except S3Error as e:
            print(f"获取WAV文件失败: {e}")
            return None
        finally:
            if 'response' in locals():
                response.close()
                response.release_conn()
