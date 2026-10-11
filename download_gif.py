import requests
import re
import os

url = "https://www.deviantart.com/mewtwo365/art/Yami-Yugi-Dancing-Gif-693847241"
headers = {"User-Agent": "Mozilla/5.0"}
html = requests.get(url, headers=headers).text
match = re.search(r'\"(https://images-wixmp[^\"\']+)\"', html)

if match:
    img_url = match.group(1)
    # The URL might have html entities
    img_url = img_url.replace('&amp;', '&')
    print("Downloading:", img_url)
    res = requests.get(img_url, headers=headers)
    with open("yugi_dance.gif", "wb") as f:
        f.write(res.content)
    print("Downloaded successfully.")
else:
    print("Not found in HTML.")
