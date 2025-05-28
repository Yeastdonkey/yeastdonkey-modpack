import os
import toml
import yaml
import requests
from glob import glob
from urllib.parse import urlparse

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
MODS_YAML_PATH = os.path.join(SOURCES_DIR, "mods.yaml")
SERVER_MODS_TXT_PATH = os.path.join(SOURCES_DIR, "server-mods.txt")

def find_client_dir():
    for entry in os.listdir(ROOT_DIR):
        if entry.endswith("_client") and os.path.isdir(os.path.join(ROOT_DIR, entry)):
            return os.path.join(ROOT_DIR, entry)
    raise FileNotFoundError("No *_client directory found.")

def find_pw_tomls(client_dir):
    pw_files = []
    subdirs = ["mods", "shaderpacks", "resourcepacks"]
    for subdir in subdirs:
        pattern = os.path.join(client_dir, subdir, "*.pw.toml")
        pw_files.extend(glob(pattern))
    return pw_files

def parse_pw_toml(path):
    data = toml.load(path)
    update = data.get("update", {}).get("modrinth", {})
    download = data.get("download", {})
    filename = os.path.basename(path)
    name = filename.replace(".pw.toml", "")
    return {
        "name": name,
        "side": data.get("side", "unknown"),
        "project_id": update.get("mod-id"),
        "version_id": update.get("version"),
        "download_url": download.get("url", "")
    }

def get_project_slug(project_id):
    url = f"https://api.modrinth.com/v2/project/{project_id}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()["slug"]

def is_github_url(url):
    return "github.com" in url

def parse_github_url(url):
    parts = urlparse(url).path.strip("/").split("/")
    if "releases" in parts and "download" in parts:
        try:
            repo_index = parts.index("releases") - 2
            user = parts[repo_index]
            repo = parts[repo_index + 1]
            tag = parts[parts.index("download") + 1]
            link = f"https://github.com/{user}/{repo}"
            return link, tag
        except Exception as e:
            print(f"Failed to parse GitHub URL: {url} - {e}")
    return None, None

def main():
    os.makedirs(SOURCES_DIR, exist_ok=True)

    client_dir = find_client_dir()
    pw_files = find_pw_tomls(client_dir)

    modlist = {}

    for path in pw_files:
        try:
            mod_data = parse_pw_toml(path)
            name = mod_data["name"]
            side = mod_data["side"]
            download_url = mod_data["download_url"]

            entry = {}

            if name == "mod-loading-screen":
                side = "client"

            if is_github_url(download_url):
                link, version_tag = parse_github_url(download_url)
                if not link or not version_tag:
                    raise ValueError(f"Unable to parse GitHub info from: {download_url}")
                entry["link"] = link
                entry["version_id"] = version_tag
                entry["side"] = side
            else:
                project_id = mod_data["project_id"]
                version_id = mod_data["version_id"]

                if not project_id or not version_id:
                    raise ValueError(f"Missing project_id or version_id in {path}")

                slug = get_project_slug(project_id)
                link = f"https://modrinth.com/mod/{slug}"

                entry["link"] = link
                entry["project_id"] = project_id
                entry["version_id"] = version_id
                entry["side"] = side

            modlist[name] = entry

        except Exception as e:
            print(f"Failed to process {path}: {e}")

    with open(MODS_YAML_PATH, "w") as f:
        yaml.dump(modlist, f, sort_keys=False)

    with open(SERVER_MODS_TXT_PATH, "w") as f:
        for name, meta in modlist.items():
            if meta["side"] in ["server", "both"]:
                f.write(f"{name}\n")

if __name__ == "__main__":
    main()
