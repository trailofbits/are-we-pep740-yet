import datetime
import json

import pytz
import requests_cache

BASE_URL = "https://pypi.org"
# Provenance began to be persisted on 2024-10-03
# And `pypa/gh-action-pypi-publish` turned it automatically on 2024-10-29
ATTESTATION_ENABLEMENT = datetime.datetime(2024, 10, 29, tzinfo=datetime.timezone.utc)

PUBLISHER_URLS = (
    "https://github.com",
    "http://github.com",
    "http://gitlab.com",
    "https://gitlab.com",
)

DEPRECATED_PACKAGES = {
    "BeautifulSoup",
    "bs4",
    "distribute",
    "django-social-auth",
    "nose",
    "pep8",
    "pycrypto",
    "pypular",
    "sklearn",
}

# Keep responses for one hour
SESSION = requests_cache.CachedSession("requests-cache", expire_after=60 * 60)


def get_simple_url(package_name):
    return f"{BASE_URL}/simple/{package_name}/"


def get_json_url(package_name):
    return f"{BASE_URL}/pypi/{package_name}/json"


def _is_yanked(file):
    return bool(file.get("yanked"))


def annotate_wheels(packages):
    print("Getting wheel data...")
    num_packages = len(packages)
    for index, package in enumerate(packages):
        print(index + 1, num_packages, package["name"])
        has_provenance = False
        from_supported_publisher = False
        url = get_simple_url(package["name"])
        simple_response = SESSION.get(
            url, headers={"Accept": "application/vnd.pypi.simple.v1+json"}
        )
        if simple_response.status_code != 200:
            print(" ! Skipping " + package["name"])
            continue
        simple = simple_response.json()

        non_yanked_files = [f for f in simple["files"] if not _is_yanked(f)]
        if not non_yanked_files:
            print(" ! Skipping " + package["name"] + " (all files yanked)")
            continue

        json_response = SESSION.get(get_json_url(package["name"]))
        json_response.raise_for_status()
        json_data = json_response.json()
        info = json_data["info"]
        project_urls = info["project_urls"] or {}
        for url in project_urls.values():
            if url.startswith(PUBLISHER_URLS):
                from_supported_publisher = True

        # Use only files belonging to the latest stable version (from the JSON API)
        # so that pre-release files don't affect provenance or upload time.
        stable_filenames = {
            f["filename"] for f in json_data["releases"][info["version"]]
        }
        stable_files = [
            f for f in non_yanked_files if f["filename"] in stable_filenames
        ]
        if not stable_files:
            print(" ! Skipping " + package["name"] + " (no stable files)")
            continue

        if stable_files[-1].get("provenance", None):
            has_provenance = True

        latest_upload = max(
            datetime.datetime.fromisoformat(f["upload-time"]) for f in stable_files
        )

        package["wheel"] = has_provenance

        # Display logic. I know, I'm sorry.
        package["value"] = 1
        if has_provenance:
            package["css_class"] = "success"
            package["icon"] = "🔏"
            package["title"] = "This package provides attestations."
        elif not from_supported_publisher:
            package["css_class"] = "unsupported"
            package["icon"] = ""
            package["title"] = (
                "This package is published from a source that doesn't support attestations (yet!)"
            )
        elif latest_upload < ATTESTATION_ENABLEMENT:
            package["css_class"] = "default"
            package["icon"] = "⏰"
            package["title"] = (
                "This package was last uploaded before PEP 740 was enabled."
            )
        else:
            package["css_class"] = "warning"
            package["icon"] = ""
            package["title"] = "This package doesn't provide attestations (yet!)"


def get_top_packages():
    print("Getting packages...")

    with open("top-pypi-packages.json") as data_file:
        packages = json.load(data_file)["rows"]

    # Rename keys
    for package in packages:
        package["downloads"] = package.pop("download_count")
        package["name"] = package.pop("project")

    return packages


def not_deprecated(package):
    return package["name"] not in DEPRECATED_PACKAGES


def remove_irrelevant_packages(packages, limit):
    print("Removing cruft...")
    active_packages = list(filter(not_deprecated, packages))
    return active_packages[:limit]


def save_to_file(packages, file_name):
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    with open(file_name, "w") as f:
        f.write(
            json.dumps(
                {
                    "data": packages,
                    "last_update": now.strftime("%A, %d %B %Y, %X %Z"),
                },
                indent=1,
            )
        )
