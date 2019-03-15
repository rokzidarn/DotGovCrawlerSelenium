from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
from selenium import webdriver
import requests
from reppy.robots import Robots
from lxml import etree
import hashlib
import base64
from models import Site, Page, Image, PageData, PageType, DataType, Link
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, MetaData, Column, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, query
from sqlalchemy.dialects.mysql import TEXT, VARCHAR, INTEGER, TIMESTAMP, LONGBLOB, CHAR

# http://edmundmartin.com/multi-threaded-crawler-in-python/
class Crawler:

    def __init__(self, seed_urls, num_workers):
        self.pool = ThreadPoolExecutor(max_workers=num_workers)  # parallel crawling, multiple workers
        self.scraped_pages = set([''])  # set of already scraped pages, needed to test duplication
        self.frontier = Queue()  # BFS implementation, FIFO
        for seed in seed_urls:
            self.frontier.put(seed)

    def extract_links_images(self, base_url, driver):
        html = driver.page_source
        links = driver.find_elements_by_xpath("//a[@href]")
        images = driver.find_elements_by_xpath("//img[@src]")
        root_url = '{}://{}'.format(urlparse(base_url).scheme, urlparse(base_url).netloc)  # canonical

        m = hashlib.md5()
        encoded = bytes(html, 'utf-8')
        m.update(encoded)
        hashed = m.digest()  # hash function on HTML code, check for duplication
        # TODO: compare exact HTML code (md5 hash function) -> DB access

        try:  # quick fix for Python SSL error
            status_code = requests.get(base_url).status_code
        except:
            driver.close()
            return

        robots = Robots.fetch(root_url + '/robots.txt')  # robots.txt file
        print('ROBOTS: ', robots)
        sitemaps = list(robots.sitemaps)  # get sitemaps

        if len(sitemaps) > 0:
            r = requests.get(sitemaps[0])
            root = etree.fromstring(r.content)
            for sitemap in root:
                children = sitemap.getchildren()
                candidate = children[0].text  # if sitemap link is not in frontier, add to it
                if candidate not in self.scraped_pages:
                    self.frontier.put(candidate)

        for link in links:  # extract links
            url = link.get_attribute('href')
            if 'javascript' not in url and 'mailto' not in url and not url.startswith('#') \
                    and urlparse(url).netloc[-7:] == '.gov.si':  # URL, domain conditions

                if url.startswith('/') or url.startswith(root_url):  # solve relative links
                    # if not (re.search("#|\?", url))
                    url = urljoin(root_url, url)

                if url[-3:] == 'pdf' or url[-3:] == 'doc' or url[-3:] == 'ppt' \
                        or url[-4:] == 'pptx' or url[-4:] == 'docx':  # extract files
                    file_base64 = base64.b64encode(requests.get(url).content)
                    print('FILE: ', file_base64)
                    continue

                if url not in self.scraped_pages and robots.allowed(url, '*'):
                    self.frontier.put(url)  # if page is not duplicated and is allowed in robots.txt, add to frontier

        # TODO: onclick Javascript events (location.href or document.location)

        for image in images:
            src = image.get_attribute('src')
            if src.startswith('http'):  # only add images with URL source, discard others
                if src.startswith('/'):
                    src = urljoin(root_url, src)

                image_base64 = base64.b64encode(requests.get(src).content)
                print('IMAGE: ', image_base64)

        driver.close()

    def scrape_page(self, url):
        options = webdriver.ChromeOptions()
        options.add_argument("headless")
        options.add_experimental_option("prefs", {"profile.default_content_settings.cookies": 2})  # disable cookies
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)  # TODO: ERROR: fix stale element reference: element is not attached to page document

        try:
            driver.get(url)
            res = {'url': url, 'driver': driver}
            return res  # result passed to callback function
        except:
            print('PROBLEM: ', url)
            return

    def post_scrape_callback(self, res):
        result = res.result()
        if result:
            self.extract_links_images(result['url'], result['driver'])

    def run_crawler(self):
        while True:
            try:
                url = self.frontier.get(timeout=60)
                if url not in self.scraped_pages:
                    print('URL: ', url)
                    self.scraped_pages.add(url)
                    job = self.pool.submit(self.scrape_page, url)  # setup driver, get page from URL
                    job.add_done_callback(self.post_scrape_callback)  # get/save data to DB
            except Empty:  # if queue is empty for 60s stop crawling
                return
            except Exception as e:  # ignore all other exceptions
                print(e)
                continue


# MAIN
if __name__ == '__main__':
    # ['http://evem.gov.si', 'https://e-uprava.gov.si', 'https://podatki.gov.si', 'http://www.e-prostor.gov.si']
    seed_urls = ['http://evem.gov.si']
    s = Crawler(seed_urls, 5)  # number of workers
    s.run_crawler()
    # TODO: detect redirects
    # TODO: crawl delay
