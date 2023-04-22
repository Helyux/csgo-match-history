__author__ = "Lukas Mahler"
__version__ = "0.0.0"
__date__ = "23.04.2023"
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
from selenium.common import exceptions
from selenium.webdriver.chrome.options import Options


class ChromeDriver:

    def __init__(self, config):

        self.headless = config['headless']
        self.chrome_driver_path = self.getPath()
        self.chrome_options = self.setOptions()

        try:
            self.driver = webdriver.Chrome(options=self.chrome_options, executable_path=self.chrome_driver_path)
            self.browser_version = self.driver.capabilities['browserVersion']
            self.driver_version = self.driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0]

            if self.browser_version[0:2] != self.driver_version[0:2]:
                self.driver = self.getUpdatedDriver()

        except selenium.common.exceptions.SessionNotCreatedException:
            self.driver = self.getUpdatedDriver()

    def getUpdatedDriver(self):
        """ Get a new driver version """

        print("[*] Updating chromedriver.exe, please wait")
        self.driver.quit()
        self.getNew(self.chrome_driver_path)
        driver = webdriver.Chrome(options=self.chrome_options, executable_path=self.chrome_driver_path)
        return driver

    def getPath(self):
        """ Find current chromedriver.exe """

        driver_path = fr"{os.path.dirname(os.path.realpath(__file__))}\chromedriver.exe"
        if os.path.isfile(driver_path):
            return driver_path
        else:
            # print("[DEBUG] Chromedriver wasn't found in current working directory")
            pass

        driver_path = os.environ["temp"] + r"\Google\Chrome\Driver\chromedriver.exe"
        if os.path.isfile(driver_path):
            return driver_path
        else:
            # print(r"[DEBUG] Chromedriver wasn't found under %PROGRAMFILES(x86)%\Google\Chrome\driver")
            pass

        print("[*] Couldn't find a Chromedriver, downloading a new one")
        self.getNew(driver_path)

        return driver_path

    def setOptions(self):
        # Headless Chrome
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument("--log-level=3")  # Fatal
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_argument('--User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                                    ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36')
        return chrome_options

    @staticmethod
    def getNew(driver_path):

        driver_path = Path(driver_path)

        if driver_path.is_file():
            os.remove(driver_path)  # Remove old chromedriver.exe

        # Get the latest chrome driver version number
        url = 'https://chromedriver.storage.googleapis.com/LATEST_RELEASE'
        version_number = requests.get(url).text

        # build the download url
        url = f"https://chromedriver.storage.googleapis.com/{version_number}/chromedriver_win32.zip"

        # download the zip file using the url built above
        driver_path.parent.mkdir(parents=True, exist_ok=True)
        driver_zip = download_file(url, dest=driver_path.as_posix())

        # extract the zip file
        with zipfile.ZipFile(driver_zip, 'r') as zipf:
            zipf.extractall(path=driver_path.parent.as_posix())  # you can specify the destination folder path here

        # delete the zip file downloaded above
        os.remove(driver_zip)


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
    required = ["cookie", "steam_id", "api_key", "headless", "reset", "fetch_new", "player_min_games"]

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
