import time, requests
from bs4 import BeautifulSoup

from storages import Storage
from .base_archiver import Archiver, ArchiveResult

from configs import WaybackConfig
from loguru import logger


class WaybackArchiver(Archiver):
    name = "wayback"

    def __init__(self, storage: Storage, driver, config: WaybackConfig):
        super(WaybackArchiver, self).__init__(storage, driver)
        self.config = config
        self.seen_urls = {}

    def download(self, url, check_if_exists=False):
        if check_if_exists and url in self.seen_urls:
            return self.seen_urls[url]

        ia_headers = {
            "Accept": "application/json",
            "Authorization": f"LOW {self.config.key}:{self.config.secret}"
        }

        r = requests.post(
            'https://web.archive.org/save/', headers=ia_headers, data={'url': url})

        if r.status_code != 200:
            logger.warning(f"Internet archive failed with status of {r.status_code}")
            return ArchiveResult(status="Internet archive failed")

        if 'job_id' not in r.json() and 'message' in r.json():
            logger.warning(f"Internet archive failed json \n {r.json()}")
            return ArchiveResult(status=f"Internet archive failed: {r.json()['message']}")

        job_id = r.json()['job_id']

        status_r = requests.get('https://web.archive.org/save/status/' + job_id, headers=ia_headers)

        retries = 0

        # wait 90-120 seconds for the archive job to finish
        while (status_r.status_code != 200 or status_r.json()['status'] == 'pending') and retries < 30:
            time.sleep(3)

            try:
                status_r = requests.get(
                    'https://web.archive.org/save/status/' + job_id, headers=ia_headers)
            except:
                time.sleep(1)

            retries += 1

        if status_r.status_code != 200:
            return ArchiveResult(status="Internet archive failed")

        status_json = status_r.json()

        if status_json['status'] != 'success':
            return ArchiveResult(status='Internet Archive failed: ' + str(status_json))

        archive_url = 'https://web.archive.org/web/' + \
            status_json['timestamp'] + '/' + status_json['original_url']

        try:
            r = requests.get(archive_url)

            parsed = BeautifulSoup(r.content, 'html.parser')

            title = parsed.find_all('title')[0].text

            if title == 'Wayback Machine':
                title = 'Could not get title'
        except:
            title = "Could not get title"

        screenshot = self.get_screenshot(url)
        result = ArchiveResult(status='success', cdn_url=archive_url, title=title, screenshot=screenshot)
        self.seen_urls[url] = result
        return result
