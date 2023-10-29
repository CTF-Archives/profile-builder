import os
import json
import docker
import logging
import tarfile
from core.banner import deb_searcher

banner_release = "ubuntu"
banner_kernel = "6.2.0-35-generic"

with open("./src/repository-list.json", "r") as f:
    key_repository = json.loads(f.read())


class Core_Builder:
    def __init__(self, banner_release: str, banner_kernel: str) -> None:
        # 默认使用本地docker服务
        self.client = docker.from_env()
        self.banner_release = banner_release
        self.banner_kernel = banner_kernel

    def container_start(self):
        container_params = {
            "image": "ubuntu:latest",  # 替换为你想要启动的Docker镜像的名称和标签
            "command": "sleep infinity",  # 替换为要在容器内运行的命令
            "detach": True,  # 设置为True以在后台运行容器
            "name": "profile-builder-{release}-{kernel}".format(release=banner_release, kernel=banner_kernel),
        }
        self.container_name = container_params["name"]

        # 启动容器
        self.container = self.client.containers.run(**container_params)

    def container_change_repository(self):
        match self.banner_release:
            case "ubuntu":
                logging.info("[+] {}".format("sed -i 's@//.*archive.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list"))
                self.container.exec_run("sed -i 's@//.*archive.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list")
                logging.info("[+] {}".format("sed -i 's@//.*security.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list"))
                self.container.exec_run("sed -i 's@//.*security.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list")
        exec_result = self.container.exec_run("apt-get update")
        logging.debug(exec_result.output.decode("utf-8").strip())

    def container_install_dependency(self):
        dependency_ubuntu = ["wget", "unzip", "dwarfdump", "build-essential", "kmod", "linux-base", "gcc-10", "gcc-11", "gcc-12"]
        match self.banner_release:
            case "ubuntu":
                logging.info("[+] {}".format("apt-get install -y " + " ".join(dependency_ubuntu)))
                exec_result = self.container.exec_run("apt-get install -y " + " ".join(dependency_ubuntu))
                logging.debug(exec_result.output.decode("utf-8").strip())

    def container_install_debs(self):
        repository_url = key_repository[banner_release]
        self.container.exec_run("mkdir /src")
        debs = deb_searcher(banner_release, banner_kernel)
        debs.sort()
        for deb in debs:
            logging.info("[+] {}".format("wget " + repository_url + deb))
            exec_result = self.container.exec_run("wget " + repository_url + deb + " -P /src/")
            logging.debug(exec_result.output.decode("utf-8").strip())

        for i in [_ for _ in debs if _.startswith("linux-modules")]:
            logging.info("dpkg -i /src/{}".format(i))
            exec_result = self.container.exec_run("dpkg -i /src/{}".format(i))
            logging.debug(exec_result.output.decode("utf-8").strip())

        for i in [_ for _ in debs if _.startswith("linux-headers")][::-1]:
            logging.info("dpkg -i /src/{}".format(i))
            exec_result = self.container.exec_run("dpkg -i /src/{}".format(i))
            logging.debug(exec_result.output.decode("utf-8").strip())

        for i in [_ for _ in debs if _.startswith("linux-image")]:
            logging.info("dpkg -i /src/{}".format(i))
            exec_result = self.container.exec_run("dpkg -i /src/{}".format(i))
            logging.debug(exec_result.output.decode("utf-8").strip())

    def container_build_dwarf(self):
        # logging.info("unpak source code")
        self.container.exec_run("mkdir /src")
        path_tool = "tool.zip.tar"
        path_dest = "/src/tool.zip"
        path_current = os.getcwd()
        with open(path_current + "/src/" + path_tool, "rb") as f:
            self.container.put_archive(os.path.dirname(path_dest), f.read())

        exec_result = self.container.exec_run('bash -c "cd /src;unzip tool.zip"')
        logging.debug(exec_result.output.decode("utf-8").strip())
        self.container.exec_run("sed -i 's/$(shell uname -r)/{}/g' /src/linux/Makefile".format(self.banner_kernel))
        self.container.exec_run('bash -c "echo TU9EVUxFX0xJQ0VOU0UoIkdQTCIpOw== | base64 -d >> /src/linux/module.c"')
        exec_result = self.container.exec_run('bash -c "cd /src/linux;make"')
        logging.debug(exec_result.output.decode("utf-8").strip())

    def extract_dwarf(self):
        archive, stats = self.client.api.get_archive(container=self.container_name, path="/src/linux/module.dwarf")

        folder_path = os.getcwd() + "/output"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        else:
            with open(os.getcwd() + "/output/module.dwarf", "wb") as f:
                for chunk in archive:
                    f.write(chunk)

    def container_clean(self):
        self.container.stop()
        self.container.remove()

    def run(self):
        logging.info("### Container starting")
        self.container_start()
        logging.info("### Change to mirror repository")
        self.container_change_repository()
        logging.info("### Install dependency")
        self.container_install_dependency()
        logging.info("### Download needful debs")
        self.container_install_debs()
        logging.info("### Build dwarf")
        self.container_build_dwarf()
        logging.info("### Extract dwarf file")
        self.extract_dwarf()
        logging.info("### Clean Container")
        self.container_clean()


if __name__ == "__main__":
    builder = Core_Builder(banner_release, banner_kernel)
    builder.run()
