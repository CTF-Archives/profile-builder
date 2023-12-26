import os
import json
import docker
import logging
import tarfile
import zipfile
import io
from core.banner import deb_searcher

with open("./src/repository-list.json", "r") as f:
    key_repository = json.loads(f.read())


class Core_Builder:
    def __init__(self, banner_release: str, banner_kernel: str) -> None:
        # 默认使用本地docker服务
        self.client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
        self.banner_release = banner_release
        self.banner_kernel = banner_kernel
        self.output_folder = os.path.join(os.getcwd(), "output")
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

    def container_start(self):
        container_params = {
            "image": "ubuntu:latest",  # 替换为你想要启动的Docker镜像的名称和标签
            "command": "sleep infinity",  # 替换为要在容器内运行的命令
            "detach": True,  # 设置为True以在后台运行容器
            "name": "profile-builder-{release}-{kernel}".format(release=self.banner_release, kernel=self.banner_kernel),
        }
        self.container_name = container_params["name"]

        # 启动容器
        self.container = self.client.containers.run(**container_params)

    def container_change_repository(self):
	    if self.banner_release == "ubuntu":
	        logging.info("[+] {}".format("sed -i 's@//.*archive.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list"))
	        self.container.exec_run("sed -i 's@//.*archive.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list")
	        logging.info("[+] {}".format("sed -i 's@//.*security.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list"))
	        self.container.exec_run("sed -i 's@//.*security.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list")
	    exec_result = self.container.exec_run("apt-get update")
	    logging.debug(exec_result.output.decode("utf-8").strip())

    def container_install_dependency(self):
	    dependency_ubuntu = ["wget", "unzip", "dwarfdump", "build-essential", "kmod", "linux-base", "gcc-10", "gcc-11", "gcc-12"]
	    if self.banner_release == "ubuntu":
	        logging.info("[+] {}".format("apt-get install -y " + " ".join(dependency_ubuntu)))
	        exec_result = self.container.exec_run("apt-get install -y " + " ".join(dependency_ubuntu))
	        logging.debug(exec_result.output.decode("utf-8").strip())

    def container_install_debs(self):
        repository_url = key_repository[self.banner_release]
        self.container.exec_run("mkdir /src")
        debs = deb_searcher(self.banner_release, self.banner_kernel)
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


    def extract_and_write_file(self, source_path, target_path):
        bits, _ = self.container.get_archive(source_path)

        file_like_object = io.BytesIO()
        for chunk in bits:
            file_like_object.write(chunk)
        file_like_object.seek(0)

        with tarfile.open(fileobj=file_like_object, mode='r:*') as tar:
            member = tar.next()

            if member is not None:
                file_data = tar.extractfile(member).read()
                with open(target_path, 'wb') as f:
                    f.write(file_data)


    def extract_dwarf(self):
        self.extract_and_write_file(source_path="/src/linux/module.dwarf",
                                    target_path=self.output_folder + "/module.dwarf")

    def extract_System_map(self):
        system_map_path = f"/boot/System.map-{self.banner_kernel}"
        system_map_filename = os.path.basename(system_map_path)

        self.extract_and_write_file(system_map_path, os.path.join(self.output_folder, system_map_filename))


    def Zip_profile(self):
        dwarf_path = os.path.join(self.output_folder, "module.dwarf")
        system_map_path = os.path.join(self.output_folder, f"System.map-{self.banner_kernel}")
        zip_filename = os.path.join(self.output_folder, f"{self.banner_release}_{self.banner_kernel}.zip")

        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(dwarf_path, arcname='module.dwarf')
            zipf.write(system_map_path, arcname=f"System.map-{self.banner_kernel}")

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
        logging.info("### Extract System.map file")
        self.extract_System_map()
        logging.info("### Zip profile")
        self.Zip_profile()
        logging.info("### Clean Container")
        self.container_clean()
