__author__ = "Lukas Mahler"
__version__ = "0.0.0"
__date__ = "11.04.2022"
__email__ = "m@hler.eu"
__status__ = "Development"

import re
import os
import json
import time
import glob
import random
import lxml.html
from tqdm import tqdm
from pathlib import Path
from datetime import timedelta
import selenium.common.exceptions

# Custom
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

# Self
from src import util


def get_matches():
    print("[*] Getting latest match data")

    driver_class = util.ChromeDriver(config)
    driver = driver_class.driver

    url = f"https://steamcommunity.com/profiles/{config['steam_id']}/gcpd/730?tab=matchhistorycompetitive"

    if config['cookie'] == "":
        config['cookie'] = input("Please input your steamLoginSecure cookie: \n-> ")
        util.setConf(config)

    cookies = {'steamLoginSecure': config['cookie']}

    driver.get("https://steamcommunity.com/")
    for name, value in cookies.items():
        driver.add_cookie({'name': name, 'value': value})
    time.sleep(1)

    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(ec.element_to_be_clickable((By.ID, "load_more_button")))
    except selenium.common.exceptions.TimeoutException:
        print("[Err] 'steamLoginSecure' cookie is probably expired")
        config['cookie'] = ''
        util.setConf(config)
        driver.quit()
        exit(1)

    last_loaded = get_last_match_data()

    if not last_loaded:
        print("[*] Looks like it's your first time using csgo-match-history, trying to load all games")

    i = 1
    while True:

        print(f"\r[*] Loading matches [~{i * 8}]", end='', flush=True)

        # Check if we need to load more
        if last_loaded:
            found_last_loaded = driver.find_elements_by_xpath(f"//*[contains(text(), '{last_loaded}')]")
            if found_last_loaded:
                print("\n[*] All new matches loaded")
                break

        try:
            element_load_more = WebDriverWait(driver, 15).until(
                ec.element_to_be_clickable((By.ID, "load_more_button"))
            )
            element_load_more.click()
            time.sleep(random.random())

        except selenium.common.exceptions.ElementClickInterceptedException:
            print("\n[Err] Couldn't get all games due to a steam error, try again later")
            driver.quit()
            exit(1)

        except selenium.common.exceptions.TimeoutException:
            print("\n[*] Probably all matches loaded")
            driver.quit()
            break

        i += 1

    print("[*] Getting page source")
    time.sleep(1)
    html = driver.page_source
    doc = lxml.html.fromstring(html)
    driver.quit()

    table_history = doc.xpath('//*[@id="personaldata_elements_container"]/table/tbody')[0]
    xml = [match for match in table_history.xpath("./tr")]
    xml.pop(0)  # Remove the headline

    save_xml_to_disk(xml)


def get_last_match_data():
    if os.path.exists("./xml"):
        latest = os.listdir("./xml")[-1]
        latest = latest[:-4]  # remove .xml
        latest = latest.split("_")
        xtime = latest[1]
        latest[1] = ':'.join(xtime[i:i+2] for i in range(0, len(xtime), 2))
        return ' '.join(latest)
    else:
        return None


def get_valid_filename(s):
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)


def save_xml_to_disk(matches):
    Path("./xml").mkdir(parents=True, exist_ok=True)

    # TODO check if we got any new matches, if we dont, abort, also dont overwrite, see below

    i = 0
    print("[*] Saving .xml to disk")
    for match in tqdm(matches, bar_format='{l_bar}{bar}', ncols=30):
        i += 1
        try:
            game_date = match.xpath(".//td[1]/table/tbody/tr[2]/td")[0].text_content().strip()
            clean_game_date = get_valid_filename(game_date)

            with open(f"./xml/{clean_game_date}.xml", 'wb') as f:
                f.write(lxml.html.tostring(match))

        except Exception as e:
            print(e)
            continue


def download_demo(url=None, matchid=None, outcomeid=None, token=None):
    Path("./demos").mkdir(parents=True, exist_ok=True)

    # url = 'http://replay190.valve.net/730/003540319049349071083_1642207433.dem.bz2'  # Example

    if url:

        # Check if we haven't downloaded the demo yet
        filename = url.split("/")[-1]
        if os.path.exists(f"./demos/{filename}"):
            # print("[*] Demo already downloaded")
            return
        else:
            # We didn't so start the download
            util.download_file(url, "./demos/")
            print("[*] Finished downloading demo")


def check_matches():
    print("[*] Checking all match .xml files")
    Path("./json").mkdir(parents=True, exist_ok=True)

    for match_xml in glob.glob("./xml/*.xml"):
        with open(match_xml, 'r') as xmlf:
            with open(f"./json/{os.path.basename(xmlf.name)[:-4]}.json", 'w') as jsonf:
                json.dump(format_matchinfo(xmlf), jsonf, indent=4)


def check_winning(match_score, player_index):

    if match_score == "15:15":
        outcome = "Draw"
    else:
        if player_index > 5:
            side = "right"
        else:
            side = "left"

        score = match_score.split(":")
        if score[0] == "16" and side == "left":
            outcome = "Win"
        elif score[1] == "16" and side == "right":
            outcome = "Win"
        else:
            outcome = "Lose"

    # print(f"[DEBUG] {match_score} / {player_index} / {side} / {outcome}")

    return outcome


def format_matchinfo(xmlf):

    matchinfo = {}
    match = lxml.html.parse(xmlf)

    # General Match Info
    inner_left_tds = match.xpath('.//table[@class="csgo_scoreboard_inner_left"]//td')
    match_map = inner_left_tds[0].text_content().replace("Competitive", "").strip()
    match_time_qued = inner_left_tds[3].text_content().strip().split(" ")[-1]
    match_time_played = inner_left_tds[4].text_content().strip().split(" ")[-1]
    match_score = match.xpath('.//td[@class="csgo_scoreboard_score"]')[0].text_content().strip().replace(" ", "")

    if len(inner_left_tds[-1].xpath('.//a')) > 0:
        url = inner_left_tds[-1].xpath('.//a')[0].get("href")
        download_demo(url=url)

    matchinfo_json = {
        'xmap': match_map,
        'score': match_score,
        'time_que': match_time_qued,
        'time_played': match_time_played
    }

    matchinfo['general'] = matchinfo_json

    # Player Info
    inner_right_trs = match.xpath('.//table[@class="csgo_scoreboard_inner_right"]//tr')
    inner_right_trs.pop(0)  # Remove Headings
    inner_right_trs.pop(5)  # Remove Score

    playerinfos = {}
    player_index = 1
    for playerinfo in inner_right_trs:
        steam_id = playerinfo.xpath('.//a')[0].get("href").split("/")[-1]

        # Check if i was on losing or winning side
        if steam_id == "sorryvirgin":
            outcome = check_winning(match_score, player_index)
            matchinfo_json['outcome'] = outcome
            matchinfo['general'] = matchinfo_json

        ping = playerinfo.xpath('.//td')[1].text_content().strip()
        kills = playerinfo.xpath('.//td')[2].text_content().strip()
        assists = playerinfo.xpath('.//td')[3].text_content().strip()
        death = playerinfo.xpath('.//td')[4].text_content().strip()
        hsp = playerinfo.xpath('.//td')[6].text_content().strip()
        score = playerinfo.xpath('.//td')[7].text_content().strip()

        single_playerinfo_json = {
            'ping': ping,
            'kills': kills,
            'assists': assists,
            'death': death,
            'hs%': hsp,
            'score': score
        }
        playerinfos[steam_id] = single_playerinfo_json

        matchinfo['players'] = playerinfos
        player_index += 1

    return matchinfo


def summarize():

    stats_map = {}
    stats_overall = {'wins': 0, 'loses': 0, 'draws': 0, 'time_que': timedelta(), 'time_played': timedelta()}
    average_que_time = None
    average_play_time = None

    longest_que_time = timedelta()
    longest_play_time = timedelta()
    shortest_que_time = timedelta(days=1)
    shortest_play_time = timedelta(days=1)

    json_files = glob.glob("./json/*.json")  # [-100:] # last 100 only
    n_matches = len(json_files)
    print(f"[*] Summarizing data from [{n_matches}] matches")
    for match_json in json_files:
        with open(match_json, 'r') as jf:
            data = json.load(jf)

            matchinfo = data['general']
            xmap = matchinfo['xmap']

            if xmap not in stats_map:
                stats_map[xmap] = {
                    'wins': 0,
                    'loses': 0,
                    'draws': 0,
                    'time_que': 0,
                    'time_played': 0
                }

            if matchinfo['outcome'] == "Win":
                stats_overall['wins'] += 1
                stats_map[xmap]['wins'] += 1
            elif matchinfo['outcome'] == "Lose":
                stats_overall['loses'] += 1
                stats_map[xmap]['loses'] += 1
            elif matchinfo['outcome'] == "Draw":
                stats_overall['draws'] += 1
                stats_map[xmap]['draws'] += 1

            m, s = matchinfo['time_que'].split(":")
            que_timedelta = timedelta(minutes=int(m), seconds=int(s))
            m, s = matchinfo['time_played'].split(":")
            played_timedelta = timedelta(minutes=int(m), seconds=int(s))

            # longest / shortest
            if que_timedelta > longest_que_time:
                longest_que_time = que_timedelta

            if que_timedelta < shortest_que_time:
                shortest_que_time = que_timedelta

            if played_timedelta > longest_play_time:
                longest_play_time = played_timedelta

            if played_timedelta < shortest_play_time:
                shortest_play_time = played_timedelta

            stats_overall['time_que'] += que_timedelta
            stats_overall['time_played'] += played_timedelta

    # Calculate overall winrate
    stats_overall['winrate'] = int(stats_overall['wins'] / (n_matches - stats_overall['draws']) * 100)

    # Calculate overall que and play time average
    stats_overall['time_que_average'] = stats_overall['time_que'] / n_matches
    stats_overall['time_played_average'] = stats_overall['time_played'] / n_matches

    # Calculate winrate per map
    for xmap in stats_map:
        n_map_matches = stats_map[xmap]['wins'] + stats_map[xmap]['loses']  # stats_map[xmap]['draws']
        stats_map[xmap]['winrate'] = int((stats_map[xmap]['wins'] / n_map_matches) * 100) # noqa

    util.newline()
    print(f" |-------------|---W---L---D-|-Win%-|")
    for xmap in stats_map:
        print(f" |_ {xmap:10s} | "
              f"{stats_map[xmap]['wins']:3d} "
              f"{stats_map[xmap]['loses']:3d} "
              f"{stats_map[xmap]['draws']:3d} | "
              f"{stats_map[xmap]['winrate']:3d}% |")
    print(f" |----------------------------------|\n |_ Total      | "
          f"{stats_overall['wins']:3d} "
          f"{stats_overall['loses']:3d} "
          f"{stats_overall['draws']:3d} | "
          f"{stats_overall['winrate']:3d}% |")

    util.newline()
    print(util.format_single_stat("Total que time", stats_overall['time_que']))
    print(util.format_single_stat("Average que time", stats_overall['time_que_average']))
    print(util.format_single_stat("Longest que time", longest_que_time))
    print(util.format_single_stat("Shortest que time", shortest_que_time))
    util.newline()
    print(util.format_single_stat("Total play time", stats_overall['time_played']))
    print(util.format_single_stat("Average play time", stats_overall['time_played_average']))
    print(util.format_single_stat("Longest play time", longest_play_time))
    print(util.format_single_stat("Shortest play time", shortest_play_time))


def main():

    # Load toml config
    global config
    config = util.getConf("prod.toml")

    if config['reset']:
        print("[*] Resetting data folders")
        util.deldir("./json")
        util.deldir("./xml")
        config['reset'] = False
        util.setConf(config)

    get_matches()
    check_matches()
    summarize()


if __name__ == '__main__':
    main()
