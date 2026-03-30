import urllib.request, json
req = urllib.request.Request("https://www.shanethegamer.com/wp-json/wp/v2/posts?slug=jack-black-yakuza-role", headers={"User-Agent": "Mozilla/5.0"})
data = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))[0]

print("Keys:", data.keys())

if "yoast_head_json" in data:
    print("yoast_head_json exists! Title:", data["yoast_head_json"].get("title"))
    
if "excerpt" in data:
    print("Excerpt:", data["excerpt"].get("rendered"))

print("Title defined in WP API:", data.get("title", {}).get("rendered"))
