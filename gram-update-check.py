import requests
import os
import hashlib
import json
from datetime import datetime, timezone
import sys


# 仓库信息
owner = "amzxyz"
repo = "RIME-LMDG"
tag = "LTS"
# 二进制文件 URL
binary_url = "https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram"
# 目标文件名
target_file = "wanxiang-lts-zh-hans.gram"
# 临时文件名
temp_file = f"{target_file}.tmp"
# 本地时间记录文件
time_record_file = "release_time_record.json"


def get_release_info():
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    response = requests.get(url)
    if response.status_code == 200:
        release_info = response.json()
        for asset in release_info.get("assets", []):
            if asset["name"] == os.path.basename(binary_url):
                return {
                    "published_at": asset["updated_at"],  # 使用 Assets 的更新时间
                    "assets": release_info["assets"]
                }
        print(f"未找到对应的 Assets: {os.path.basename(binary_url)}")
        return None
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return None


def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        return None


def download_file(url, file_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded_size = 0
        with open(file_path, 'wb') as f:
            for data in response.iter_content(block_size):
                f.write(data)
                downloaded_size += len(data)
                progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                sys.stdout.write(f"\r下载进度: {progress:.2f}%")
                sys.stdout.flush()
        sys.stdout.write("\n")
        if total_size != 0 and downloaded_size != total_size:
            print("下载出错，文件大小不匹配。")
            return False
        return True
    except requests.RequestException as e:
        print(f"下载文件时出错: {e}")
        return False


def save_time_record(mode, release_published_at):
    if mode == "record_file":
        # 更新时间记录
        print(f"正在将更新时间记录到 {time_record_file}。")
        with open(time_record_file, "w") as f:
            json.dump({"published_at": release_published_at.strftime("%Y-%m-%dT%H:%M:%SZ")}, f)

def update_file_if_needed(release_published_at, mode):
    # 输出运行模式
    # print(f"运行模式: {mode}")
    # 将 release_published_at 转换为有时区信息的对象
    release_published_at = release_published_at.replace(tzinfo=timezone.utc)

    if mode == "record_file":
        if os.path.exists(target_file) and os.path.exists(time_record_file):
            with open(time_record_file, "r") as f:
                local_time = json.load(f).get("published_at")
            local_time = datetime.strptime(local_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if release_published_at <= local_time:
                print(f"文件无需更新，{target_file} 记录更新时间为 {local_time} ，release 时间为 {release_published_at}。")
                return False
        else:
            print("未找到目标文件或首次运行，将进行更新。")
    elif mode == "file_mtime":
        if os.path.exists(target_file):
            local_mtime = datetime.fromtimestamp(os.path.getmtime(target_file), timezone.utc)
            if release_published_at <= local_mtime:
                print(f"文件无需更新，{target_file} 本地修改时间为 {local_mtime} ，release 时间为 {release_published_at}。")
                return False
        else:
            print("未找到目标文件或首次运行，将进行更新。")
    else:
        print("不支持的模式，请选择 'record_file' 或 'file_mtime'。")
        return False

    # 下载到临时文件
    if download_file(binary_url, temp_file):
        temp_sha256 = calculate_sha256(temp_file)
        target_sha256 = calculate_sha256(target_file)

        if temp_sha256 != target_sha256:
            os.replace(temp_file, target_file)
            print("文件已更新。")
            print(f"下载文件的哈希值: {temp_sha256}")
            print(f"目标文件的哈希值: {target_sha256}")
            save_time_record(mode, release_published_at)
            return True
        else:
            print("-" * 50)
            print("文件内容未改变，无需更新。")
            print(f"下载文件的哈希值: {temp_sha256}")
            print(f"目标文件的哈希值: {target_sha256}")
            print("-" * 50)
            save_time_record(mode, release_published_at)
            os.remove(temp_file)
            return False


if __name__ == "__main__":
    release_info = get_release_info()
    if release_info:
        published_at = release_info.get("published_at")
        if published_at:
            release_published_at = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
            # 可以选择 "record_file" 或 "file_mtime" 模式，默认为 "record_file"
            update_file_if_needed(release_published_at, mode="record_file")
    