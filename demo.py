import docker
import os
import tarfile

# 创建 Docker 客户端
client = docker.from_env()

container_params = {
    "image": "ubuntu:latest",  # 替换为你想要启动的Docker镜像的名称和标签
    "command": "sleep infinity",  # 替换为要在容器内运行的命令
    "detach": True,  # 设置为True以在后台运行容器
}

# 创建容器并启动
container = client.containers.run(**container_params)
container.exec_run("mkdir /src")

container_dir = "/src/data.txt"
src="./data.txt"
print(os.getcwd())
os.chdir(os.path.dirname(src))
srcname = os.path.basename(src)
print(src + '.tar')
tar = tarfile.open(src + '.tar', mode='w')
try:
    tar.add(srcname)
finally:
    tar.close()

data = open(src + '.tar', 'rb').read()
container.put_archive(os.path.dirname(container_dir), data)
