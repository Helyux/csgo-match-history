__author__ = "Lukas Mahler"
__version__ = "0.0.0"
__date__ = "23.04.2022"
__email__ = "m@hler.eu"
__status__ = "Development"

import os
import json
import time
import glob
import random
from pathlib import Path
from datetime import timedelta
from collections import OrderedDict

# Custom
import lxml.html
import selenium.common.exceptions
from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

# Self
from src import util
from src import steam


def get_last_match_data():
    """
    Reformat the latest .xml file date format (YYYY-MM-DD_HHMMSS_GMT.xml) into
    the date format given by steam (YYYY-MM-DD HH:MM:SS GMT) history
    """

    p = Path("./xml")
    if p.exists() and p.is_dir():
        latest = os.listdir("./xml")[-1]
        latest = latest[:-4]  # remove .xml
        latest = latest.split("_")
        xtime = latest[1]
        latest[1] = ':'.join(xtime[i:i+2] for i in range(0, len(xtime), 2))  # Add ':' between HHMMSS
        return ' '.join(latest)  # Put it back together
    else:
        return None


def get_match_xml():
    print("[*] Getting latest match data from steam")

    driver_class = util.ChromeDriver(config)
    driver = driver_class.driver

    url = f"https://steamcommunity.com/profiles/{config['steam_id']}/gcpd/730?tab=matchhistorycompetitive"
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
        print("[*] Looks like it's your first time using csgo-match-history")
        print("    Trying to load all games, this might take a while")

    i = 0
    match_cache = []
    loading = True

    while loading:

        matches = driver.find_elements(by=By.XPATH, value='//*[@id="personaldata_elements_container"]/table/tbody/tr')

        for match in matches:
            if match in match_cache:
                continue
            else:
                print(f"\r[*] Loading matches [{i}]", end='', flush=True)

                time_element = match.find_elements(by=By.XPATH, value='.//td[1]/table/tbody/tr[2]/td')
                if time_element:
                    loaded = time_element[0].get_attribute("innerHTML").strip()
                    if loaded == last_loaded:
                        print("\n[*] All new matches loaded")
                        loading = False
                        break
                    else:
                        match_cache.append(match)  # Only append valid games
                        i += 1
                else:
                    continue

        if loading:

            try:
                element_load_more = WebDriverWait(driver, 15).until(
                    ec.element_to_be_clickable((By.ID, "load_more_button"))
                )
                element_load_more.click()
                time.sleep(random.random())

            except selenium.common.exceptions.ElementClickInterceptedException:
                print("\n[Err] Couldn't get all games due to a steam error, please try again later")
                driver.quit()
                exit(1)

            except selenium.common.exceptions.TimeoutException:
                print("\n[*] Probably all matches loaded")
                break

    if match_cache:
        save_xml_to_disk(match_cache)
    else:
        print("[*] No new matches found")

    driver.quit()


def save_xml_to_disk(matches):

    print("[*] Saving '.xml' files to disk")
    Path("./xml").mkdir(parents=True, exist_ok=True)

    for match in tqdm(matches, bar_format='{l_bar}{bar} [{n_fmt}/{total_fmt}]', ncols=50):

        game_date_elements = match.find_elements(by=By.XPATH, value='.//td[1]/table/tbody/tr[2]/td')
        game_date = game_date_elements[0].get_attribute("innerHTML").strip()
        clean_game_date = util.get_valid_filename(game_date)

        p = Path(f"./xml/{clean_game_date}.xml")

        if not p.exists():
            with open(p, 'w', encoding='UTF-8') as f:
                f.write(match.get_attribute('outerHTML'))

    time.sleep(0.1)


def match_xml_to_json():
    print("[*] Formatting and converting '.xml' files to '.json' (this can take a while on the first run)")
    time.sleep(0.1)
    Path("./json").mkdir(parents=True, exist_ok=True)

    for match_xml in tqdm(glob.glob("./xml/*.xml"), bar_format='{l_bar}{bar} [{n_fmt}/{total_fmt}]', ncols=50):

        p_xml = Path(match_xml)
        p_json = Path(f"./json/{p_xml.name[:-4]}.json")

        if not p_json.exists():
            with open(match_xml, 'r', encoding='UTF-8') as xmlf:
                with open(f"./json/{os.path.basename(xmlf.name)[:-4]}.json", 'w') as jsonf:
                    json.dump(format_matchinfo(xmlf), jsonf, indent=4)


def check_winning(match_score, player_index):

    if match_score == "15:15":
        outcome = "Draw"
    else:
        if not any(x in match_score for x in ["15", "16"]):
            # Game ended early, skip these games as we got no way to determine who won on a surrender
            outcome = "Surrender"
        else:
            score = match_score.split(":")
            if score[0] == "16" and player_index < 5:
                outcome = "Win"
            elif score[1] == "16" and player_index > 5:
                outcome = "Win"
            else:
                outcome = "Lose"

    # print(f"[DEBUG] {match_score} / {player_index} / {side} / {outcome}")

    return outcome


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


def format_matchinfo(xmlf):

    matchinfo = {}
    parser = lxml.html.HTMLParser(encoding='UTF-8')
    match = lxml.html.parse(xmlf, parser=parser)

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
        steam_id = playerinfo.xpath('.//a')[0].get("href").split("/")
        steam_id = Steam.resolve_vanity_url(steam_id[-1])

        # Check if i was on losing or winning side
        if steam_id == config['steam_id']:
            outcome = check_winning(match_score, player_index)
            matchinfo_json['outcome'] = outcome
            matchinfo['general'] = matchinfo_json

        alias = playerinfo.xpath('.//a')[1].text_content().strip()
        ping = int(playerinfo.xpath('.//td')[1].text_content().strip())
        kills = int(playerinfo.xpath('.//td')[2].text_content().strip())
        assists = int(playerinfo.xpath('.//td')[3].text_content().strip())
        death = int(playerinfo.xpath('.//td')[4].text_content().strip())
        raw_mvps = playerinfo.xpath('.//td')[5].text_content().strip()
        mvps = 0 if not raw_mvps else 1 if raw_mvps == "★" else int(raw_mvps.replace("★", ""))
        hsp = playerinfo.xpath('.//td')[6].text_content().strip()[:-1]  # Remove the %
        hsp = int(hsp) if hsp else 0
        score = int(playerinfo.xpath('.//td')[7].text_content().strip())

        single_playerinfo_json = {
            'alias': alias,
            'ping': ping,
            'kills': kills,
            'assists': assists,
            'death': death,
            'mvps': mvps,
            'hs%': hsp,
            'score': score
        }
        playerinfos[steam_id] = single_playerinfo_json

        matchinfo['players'] = playerinfos
        player_index += 1

    return matchinfo


def summarize():

    stats_map = {}
    stats_players = {}
    stats_overall = {'games': 0, 'wins': 0, 'loses': 0, 'draws': 0, 'surrenders': 0,
                     'time_que': timedelta(), 'time_played': timedelta()}

    longest_que_time = timedelta()
    longest_play_time = timedelta()
    shortest_que_time = timedelta(days=1)
    shortest_play_time = timedelta(days=1)

    json_files = glob.glob("./json/*.json")  # [-100:] # last 100 only
    n_matches = len(json_files)

    if n_matches == 0:
        print("[Err] Can't summarize from zero matches")
        exit(1)

    print(f"[*] Summarizing data from [{n_matches}] match '.json' files")
    for match_json in json_files:
        with open(match_json, 'r') as jf:
            data = json.load(jf)

            matchinfo = data['general']
            playerinfo = data['players']
            xmap = matchinfo['xmap']

            if xmap not in stats_map:

                # Init new map dict if it doesnt exist yet
                stats_map[xmap] = {
                    'games': 0,
                    'wins': 0,
                    'loses': 0,
                    'draws': 0,
                    'surrenders': 0,
                    'time_que': timedelta(),
                    'time_played': timedelta()
                }

            stats_overall['games'] += 1
            stats_map[xmap]['games'] += 1

            if matchinfo['outcome'] == "Win":
                stats_overall['wins'] += 1
                stats_map[xmap]['wins'] += 1
            elif matchinfo['outcome'] == "Lose":
                stats_overall['loses'] += 1
                stats_map[xmap]['loses'] += 1
            elif matchinfo['outcome'] == "Draw":
                stats_overall['draws'] += 1
                stats_map[xmap]['draws'] += 1
            elif matchinfo['outcome'] == "Surrender":
                stats_overall['surrenders'] += 1
                stats_map[xmap]['surrenders'] += 1

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
            stats_map[xmap]['time_que'] += que_timedelta
            stats_map[xmap]['time_played'] += played_timedelta

            # Playerinfo
            for steam_id in playerinfo:
                if steam_id not in stats_players:

                    # Init new player dict if it doesnt exist yet
                    stats_players[steam_id] = {
                        'alias': "",
                        'games': 0,
                        'ping': 0,
                        'kills': 0,
                        'assists': 0,
                        'death': 0,
                        'mvps': 0,
                        'hs%': 0,
                        'score': 0
                    }

                stats_players[steam_id]['alias'] = playerinfo[steam_id]['alias']
                stats_players[steam_id]['games'] += 1
                stats_players[steam_id]['ping'] += playerinfo[steam_id]['ping']
                stats_players[steam_id]['kills'] += playerinfo[steam_id]['kills']
                stats_players[steam_id]['assists'] += playerinfo[steam_id]['assists']
                stats_players[steam_id]['death'] += playerinfo[steam_id]['death']
                stats_players[steam_id]['mvps'] += playerinfo[steam_id]['mvps']
                stats_players[steam_id]['hs%'] += playerinfo[steam_id]['hs%']
                stats_players[steam_id]['score'] += playerinfo[steam_id]['score']

    # Sort map and players dict by games played
    stats_map = OrderedDict(sorted(stats_map.items(), key=lambda x: x[1]['games'], reverse=True))
    stats_players = OrderedDict(sorted(stats_players.items(), key=lambda x: x[1]['games'], reverse=True))

    # Calculate overall [winrate, que and play time average]
    stats_overall['winrate'] = int(stats_overall['wins'] / (stats_overall['games'] - (stats_overall['draws'] + stats_overall['surrenders'])) * 100) # noqa
    stats_overall['time_que_average'] = stats_overall['time_que'] / stats_overall['games']
    stats_overall['time_played_average'] = stats_overall['time_played'] / stats_overall['games']

    # Calculate per map [play%, winrate, que and play time average]
    for xmap in stats_map:
        stats_map[xmap]['play%'] = int(stats_map[xmap]['games'] / stats_overall['games'] * 100)
        stats_map[xmap]['winrate'] = int(stats_map[xmap]['wins'] / (stats_map[xmap]['games'] - (stats_map[xmap]['draws'] + stats_map[xmap]['surrenders'])) * 100) # noqa
        stats_map[xmap]['time_que_average'] = stats_map[xmap]['time_que'] / stats_map[xmap]['games']
        stats_map[xmap]['time_played_average'] = stats_map[xmap]['time_played'] / stats_map[xmap]['games']

    util.newline()
    print(f" |--Map--------|---G-----%--|---W---L---D---S-|-Win%-|")
    for xmap in stats_map:
        print(f" |_ {xmap:10s} | "
              f"{stats_map[xmap]['games']:3d} "
              f"({stats_map[xmap]['play%']:3d}%) | "
              f"{stats_map[xmap]['wins']:3d} "
              f"{stats_map[xmap]['loses']:3d} "
              f"{stats_map[xmap]['draws']:3d} "
              f"{stats_map[xmap]['surrenders']:3d} | "
              f"{stats_map[xmap]['winrate']:3d}% |")
    print(f" |---------------------------------------------------|\n |_ Total      | "
          f"{stats_overall['games']:3d}        | "
          f"{stats_overall['wins']:3d} "
          f"{stats_overall['loses']:3d} "
          f"{stats_overall['draws']:3d} "
          f"{stats_overall['surrenders']:3d} | "
          f"{stats_overall['winrate']:3d}% |")

    util.newline()

    print(f" |--Map--------|---G-|-Total Que--|-Total Play-|-Avg Que--|-Avg Play-|")
    for xmap in stats_map:
        print(f" |_ {xmap:10s} | "
              f"{stats_map[xmap]['games']:3d} | "
              f"{util.strfdelta(stats_map[xmap]['time_que'], '%{D}d %H:%{M}h')} | "
              f"{util.strfdelta(stats_map[xmap]['time_played'], '%{D}d %H:%{M}h')} | "
              f"{util.strfdelta(stats_map[xmap]['time_que_average'], '%M:%{S}min')} | "
              f"{util.strfdelta(stats_map[xmap]['time_played_average'], '%M:%{S}min')} |")
    print(f" |-------------------------------------------------------------------|")

    util.newline()
    print("Fun Stats\n-----------------------------------")
    print(util.format_single_stat("Total que time", stats_overall['time_que']))
    print(util.format_single_stat("Average que time", stats_overall['time_que_average']))
    print(util.format_single_stat("Longest que time", longest_que_time))
    print(util.format_single_stat("Shortest que time", shortest_que_time))
    util.newline()
    print(util.format_single_stat("Total play time", stats_overall['time_played']))
    print(util.format_single_stat("Average play time", stats_overall['time_played_average']))
    print(util.format_single_stat("Longest play time", longest_play_time))
    print(util.format_single_stat("Shortest play time", shortest_play_time))

    # Print your stats
    for steam_id in stats_players:
        if stats_players[steam_id]['games'] > 2:
            print_player_stats(stats_players, steam_id)


def print_player_stats(stats_players, steam_id):

    ps = stats_players[steam_id]
    alias = ps['alias']
    ngames = ps['games']
    average_ping = ps['ping'] / ps['games']
    average_kills = ps['kills'] / ps['games']
    average_assists = ps['assists'] / ps['games']
    average_death = ps['death'] / ps['games']
    average_mvps = ps['mvps'] / ps['games']
    average_hsp = ps['hs%'] / ps['games']
    average_score = ps['score'] / ps['games']
    average_kda = f"{average_kills:.0f}/{average_death:.0f}/{average_assists:.0f}"
    kda_score = round((ps['kills'] + ps['assists']) / ps['death'], 2)

    util.newline()
    print(f"Player Stats: {alias}\n-----------------------------------")
    print(util.format_single_stat("Number of Games", ngames))
    print(util.format_single_stat("Average K/D/A", average_kda))
    print(util.format_single_stat("Average Ping", average_ping))
    # print(util.format_single_stat("Average Kills", average_kills))
    # print(util.format_single_stat("Average Assists", average_assists))
    # print(util.format_single_stat("Average Death", average_death))
    print(util.format_single_stat("Average mvps", average_mvps))
    print(util.format_single_stat("Average hsp", average_hsp) + "%")
    print(util.format_single_stat("Average Score", average_score))
    print(util.format_single_stat("KDA Score", kda_score, nround=2))


def main():

    # Load toml config
    global config
    config = util.getConf("prod.toml")

    global Steam
    Steam = steam.Steam(config['api_key'])

    if config['reset']:
        print("[*] Resetting data folders")
        util.deldir("./json")
        util.deldir("./xml")
        config['reset'] = False
        util.setConf(config)

    if config['fetch_new']:
        get_match_xml()
        match_xml_to_json()

    summarize()


if __name__ == '__main__':
    main()
