from core import *
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

if __name__ == "__main__":
    banner_release, banner_kernel = banner_analyzer(input("input:"))
    print("banner_release: {}\nbanner_kernel: {}".format(banner_release, banner_kernel))
    builder = Core_Builder(banner_release, banner_kernel)
    builder.run()
