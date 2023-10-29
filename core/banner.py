import json
import requests
import string

key_release = ["ubuntu", "debian"]
with open("./src/repository-list.json", "r") as f:
    key_repository = json.loads(f.read())


def banner_analyzer(banner: str):
    banner_release = [i for i in key_release if i in banner][0]
    banner_kernel = [i for i in banner.replace("(", " ").replace(")", " ").split(" ") if i != ""][2]

    return banner_release, banner_kernel


def deb_searcher(banner_release: str, banner_kernel: str):
    repository_url = key_repository[banner_release]
    repository_debs = requests.get(repository_url).text
    repository_debs = [i.split('"')[1] for i in [i for i in repository_debs.split("\n")[4:-3] if i != ""]]
    repository_debs_need = [
        i
        for i in repository_debs
        if ("linux-modules-" + banner_kernel in i)
        or ("linux-image" in i and banner_kernel in i)
        or ("linux-headers-" + banner_kernel[::-1].split("-", 1)[1][::-1] in i)
    ]
    return repository_debs_need


if __name__ == "__main__":
    ins = "Linux version 6.2.0-35-generic (buildd@bos03-amd64-016) (x86_64-linux-gnu-gcc-11 (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0, GNU ld (GNU Binutils for Ubuntu) 2.38) #35~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC  (Ubuntu 6.2.0-35.35~22.04.1-generic 6.2.16)"
    banner_release, banner_kernel = banner_analyzer(ins)
    deb_url = deb_searcher(banner_release, banner_kernel)
    deb_url.sort()
    print(deb_url[::-1])
