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
from sqlalchemy.orm import sessionmaker, relationship, query, scoped_session
from sqlalchemy.dialects.mysql import TEXT, VARCHAR, INTEGER, TIMESTAMP, LONGBLOB, CHAR
import datetime
import sys


# http://edmundmartin.com/multi-threaded-crawler-in-python/
class Crawler:

    def __init__(self, seed_urls, num_workers):
        self.pool = ThreadPoolExecutor(max_workers=num_workers)  # parallel crawling, multiple workers
        self.scraped_pages = set([''])  # set of already scraped pages, needed to test duplication
        self.scraped_sites = set([''])  # set of already scraped sites
        self.robots = dict()  # all robots.txt data from each site
        self.frontier = Queue()  # BFS implementation, FIFO
        for seed in seed_urls:
            self.frontier.put(seed)

    def create_session(self):
        meta = MetaData(schema="crawldb")
        Base = declarative_base(metadata=meta)
        DATABASE_URI = 'postgres+psycopg2://postgres:rokzidarn@localhost:5432/crawldb'
        engine = create_engine(DATABASE_URI)
        Base.metadata.create_all(engine)

        # Session = sessionmaker(bind=engine)

        session_factory = sessionmaker(bind=engine)

        return session_factory

    def delete_all(self):
        session_factory = self.create_session()
        Session = scoped_session(session_factory)
        session = Session()

        session.query(Image).delete()
        session.commit()
        session.query(Link).delete()
        session.commit()
        session.query(PageData).delete()
        session.commit()
        session.query(Page).delete()
        session.commit()
        session.query(Site).delete()
        session.commit()

        Session.remove()

    def insert_site(self, root_url, robots, session):
        sitemaps = list(robots.sitemaps)  # get sitemaps

        if len(sitemaps) > 0:
            r = requests.get(sitemaps[0])
            root = etree.fromstring(r.content)
            for sitemap in root:
                children = sitemap.getchildren()
                candidate = children[0].text  # if sitemap link is not in frontier, add to it
                if candidate not in self.scraped_pages:
                    self.frontier.put(candidate)

        if root_url not in self.scraped_sites:
            print('ROBOTS: ', robots)
            site = Site(
                domain=root_url,
                robots_content=str(robots),
                sitemap_content=sitemaps
            )

            session.add(site)
            session.commit()

            self.scraped_sites.add(root_url)
            site_id = site.id
        else:
            site = session.query(Site).filter(Site.domain == root_url).first()
            site_id = site.id

        return site_id

    def insert_page(self, site_id, base_url, html, session):
        try:  # quick fix (SSL error, certificate verify failed)
            status_code = requests.get(base_url).status_code
        except:
            driver.close()
            return None

        md5 = hashlib.md5()  # compare exact HTML code (md5 hash function)
        encoded = bytes(html, 'utf-8')
        md5.update(encoded)
        hashed = md5.digest()  # hash function on HTML code, check for duplication

        pages = session.query(Page).all()
        hashes = [page.hash for page in pages]
        if hashed not in hashes:
            page = Page(
                site_id=site_id,
                page_type_code='HTML',
                url=base_url,
                html_content=html,
                http_status_code=status_code,
                accessed_time=datetime.datetime.now().date(),
                hash=hashed
            )
            session.add(page)
            session.commit()
            page_id = page.id
        else:
            page = Page(
                site_id=site_id,
                page_type_code='DUPLICATE',
                url=base_url,
                http_status_code=status_code,
                accessed_time=datetime.datetime.now().date(),
                hash=hashed
            )
            session.add(page)
            session.commit()
            page_id = page.id

        return page_id

    def insert_image(self, page_id, src, encoded, session):
        content_type = src.split('.')
        filename = content_type[-2].split('/')
        #print('IMAGE: ', src)

        image = Image(
            page_id=page_id,
            filename=filename[-1],
            content_type=content_type[-1],
            data=encoded,
            accessed_time=datetime.datetime.now().date()
        )

        session.add(image)
        session.commit()

    def insert_page_data(self, site_id, url, encoded, session):
        pages = session.query(Page).all()
        urls = [page.url for page in pages]

        if url not in urls:
            content_type = url.split('.')[-1].upper()
            print('FILE: ', url)

            page = Page(
                site_id=site_id,
                page_type_code='BINARY',
                url=url,
                http_status_code=200,
                accessed_time=datetime.datetime.now().date(),
            )
            session.add(page)
            session.commit()
            page_id = page.id

            page_data = PageData(
                page_id=page_id,
                data_type_code=content_type,
                data=encoded
            )
            session.add(page_data)
            session.commit()

    def extract_links_images(self, base_url, driver, robots):
        html = driver.page_source
        links = driver.find_elements_by_xpath("//a[@href]")
        images = driver.find_elements_by_xpath("//img[@src]")
        root_url = '{}://{}'.format(urlparse(base_url).scheme, urlparse(base_url).netloc)  # canonical

        session_factory = self.create_session()
        Session = scoped_session(session_factory)
        session = Session()

        site_id = self.insert_site(root_url, robots, session)
        page_id = self.insert_page(site_id, base_url, html, session)

        if page_id is not None:
            for link in links:  # extract links
                url = link.get_attribute('href')
                if 'javascript' not in url and 'mailto' not in url and not url.startswith('#') \
                    and urlparse(url).netloc[-7:] == '.gov.si' \
                    and urlparse(url).netloc[-4:] != '.zip' and urlparse(url).netloc[-4:] != '.cls':
                    # URL, domain conditions

                    if url.startswith('/') or url.startswith(root_url):  # solve relative links
                        # if not (re.search("#|\?", url))
                        url = urljoin(root_url, url)

                    if url[-3:] == 'pdf' or url[-3:] == 'doc' or url[-3:] == 'ppt' \
                            or url[-4:] == 'pptx' or url[-4:] == 'docx':  # extract files

                        file_base64 = base64.b64encode(requests.get(url).content)
                        self.insert_page_data(site_id, url, file_base64, session)
                        continue

                    if url not in self.scraped_pages and robots.allowed(url, '*') and ('#' not in url):
                        self.frontier.put(url)  # if page is not duplicated and is allowed in robots, add to frontier

            image_sources = list()
            for image in images:
                src = image.get_attribute('src')
                if src.startswith('http') and src not in image_sources:
                    # only add non duplicated images with URL source, discard others
                    if src.startswith('/'):
                        src = urljoin(root_url, src)

                    image_base64 = base64.b64encode(requests.get(src).content)
                    self.insert_image(page_id, src, image_base64, session)
                    image_sources.append(src)

        Session.remove()
        driver.close()

    def scrape_page(self, url):
        options = webdriver.ChromeOptions()
        options.add_argument("headless")
        options.add_experimental_option("prefs", {"profile.default_content_settings.cookies": 2})  # disable cookies
        driver = webdriver.Chrome(options=options)
        root_url = '{}://{}'.format(urlparse(url).scheme, urlparse(url).netloc)  # canonical

        if root_url in self.robots:
            robots = self.robots.get(root_url)
        else:
            robots = Robots.fetch(root_url + '/robots.txt')
            self.robots.update({root_url: robots})

        cdelay = robots.agent('*').delay
        if cdelay is None:
            crawl_delay = 5
        else:
            crawl_delay = int(cdelay)

        driver.implicitly_wait(crawl_delay)

        try:
            driver.get(url)
            res = {'url': url, 'driver': driver, 'robots': robots}
            return res  # result passed to callback function
        except:
            print('PROBLEM: ', url)
            return

    def post_scrape_callback(self, res):
        result = res.result()
        if result:
            self.extract_links_images(result['url'], result['driver'], result['robots'])

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
                session.close()
                return
            except Exception as e:  # ignore all other exceptions
                print(e)
                continue


# MAIN
if __name__ == '__main__':
    seeds = ['https://e-uprava.gov.si', 'https://podatki.gov.si', 'http://www.e-prostor.gov.si']  # 'http://evem.gov.si'
    crawl = Crawler(seeds, 5)  # number of workers
    # sys.stdout = open('data/stdout.txt', 'w')

    crawl.delete_all()
    crawl.run_crawler()  # SELECT sum(numbackends) FROM pg_stat_database;

    # TODO: Links table (+ composite PK)
    # TODO: onclick Javascript events (location.href or document.location)
    # TODO: visualization - Gephi
