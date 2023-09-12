__author__ = "Lukas Mahler"
__version__ = "0.0.0"
__date__ = "12.09.2023"
__email__ = "m@hler.eu"
__status__ = "Development"


# Default
import re
import math
import string
import shutil
import zipfile
import os.path
from pathlib import Path
from datetime import timedelta

# Custom
import toml
import requests
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class ChromeDriver:

    def __init__(self, config):

        self.headless = config['headless']
        self.chrome_options = self.setOptions()
        self.driver = webdriver.Chrome(options=self.chrome_options)

    def setOptions(self):
        # Headless Chrome
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument("--log-level=3")  # Fatal
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_argument('--User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36)')
        return chrome_options


def getConf(fname):
    """
    """
    if fname.endswith(".toml"):
        if os.path.isfile(fname):
            try:
                config = toml.load(fname)
                checkConf(config)
                return config
            except ValueError as e:
                print(f"The provided '.toml' is probably invalid, returned error:\n{e}")
                exit(1)
        else:
            print(f"Couldn't locate the '.toml' file [{fname}].")
            print("Creating a new '.toml' file from template, please edit and restart.")
            shutil.copy("src/template.toml", fname)
            exit(1)
    else:
        print(f"The provided config file [{fname}] is not a '.toml' file.")
        print("Creating a new '.toml' file from template, please edit and restart.")
        shutil.copy("src/template.toml", "prod.toml")
        exit(1)


def setConf(data, fname="prod.toml"):
    if Path(fname).is_file():
        with open(fname, 'w') as f:
            toml.dump(data, f)


def checkConf(config):
    changed = False
    required = ["cookie", "steam_id", "api_key", "headless", "reset", "fetch_new", "download_demos", "player_min_games"]

    # If we do only summarize we just need to check the "player_min_games" key
    if not config['fetch_new']:
        required = ["player_min_games"]
        return

    for required_key in required:
        if required_key not in config:
            print(f"[Err] Missing key {required_key}")
            exit(1)
        else:
            if config[required_key] == "":
                print(f"[Err] Key {required_key} can't be empty")
                user_input = input(f"[*] Please input a value for the key [{required_key}]: ").strip()
                if user_input:
                    changed = True
                    config[required_key] = user_input
                else:
                    exit(1)
    if changed:
        setConf(config)


def format_single_stat(tx, stat, nround=0, percent=False):

    if isinstance(stat, timedelta):
        stat = strfdelta(stat, "%{D}d %H:%M:%S")

    if isinstance(stat, float):
        if nround == 0:
            stat = int(round(stat, nround))
        else:
            stat = round(stat, nround)

    display_stat = str(stat)
    if percent:
        display_stat += "%"

    return f"├ {tx:20s}│ {display_stat:13s} │"


def format_timedelta(td):
    """ Round and stringify a timedelta"""
    if isinstance(td, timedelta):
        # Round up timedeltas, see https://stackoverflow.com/a/60976512/5593051
        return str(timedelta(seconds=math.ceil(td.total_seconds())))
    else:
        return None


class DeltaTemplate(string.Template):
    delimiter = "%"


def strfdelta(tdelta, fmt):
    d = {"D": f"{tdelta.days:2d}"}
    if d["D"] == " 0" and ("%{D}d" in fmt):
        fmt = fmt.replace("%{D}d", "   ")
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    d["H"] = f"{hours:02d}"
    d["M"] = f"{minutes:02d}"
    d["S"] = f"{seconds:02d}"
    t = DeltaTemplate(fmt)
    return t.safe_substitute(**d)


def newline(n=1):
    for i in range(0, n):
        print("")


def deldir(dir_to_delete):
    if dir_to_delete.startswith("."):
        dir_to_delete = dir_to_delete.replace(".", Path(os.path.dirname(os.path.realpath(__file__))).parent.as_posix())

    if Path(dir_to_delete).is_dir():
        shutil.rmtree(dir_to_delete)


def download_file(url, dest='./'):

    filename = url.split("/")[-1]
    destination = dest + filename
    response = requests.get(url, stream=True)
    total_size_in_bytes = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 Kibibyte
    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True, ncols=60)

    with open(destination, "wb") as file:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)
    progress_bar.close()
    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        print("[Err] Something went wrong")
        exit(1)

    return destination


def get_valid_filename(s):
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)


if __name__ == "__main__":
    exit()
