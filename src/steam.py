"""
TBD
"""

__author__ = "Lukas Mahler"
__version__ = "0.0.0"
__date__ = "20.04.2022"
__email__ = "m@hler.eu"
__status__ = "Development"

# Default
import json

# Custom
import requests


class Steam:

    def __init__(self, api_key):
        self.api_key = api_key
        self.cache = {}

    def resolve_vanity_url(self, vanity_url):

        # Check if it's a valid vanity_url and not a steam_id already
        try:
            int(vanity_url)
            return vanity_url
        except ValueError:
            pass

        # Check if we have't already resolved this vanity_url
        if vanity_url in self.cache:
            # print("[*] Using cached steam_id")
            return self.cache[vanity_url]
        else:
            # print(f"[*] Requesting steam_id for {vanity_url}")
            url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/" \
                  f"?key={self.api_key}&vanityurl={vanity_url}"

            req = requests.get(url)

            if req.status_code == 200:
                data = json.loads(req.text)
                steam_id = data['response']['steamid']
                self.cache[vanity_url] = steam_id
                return steam_id
            else:
                print(f"[Err] Can't resolve the vanity url [code: {req.status_code}]")
                return vanity_url


if __name__ == "__main__":
    exit()
