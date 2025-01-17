from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options, DesiredCapabilities
import requests
from reppy.robots import Robots
import hashlib
from lxml import etree
import base64
from models import Site, Page, Image, PageData, PageType, DataType, Link
import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, MetaData, Column, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, query
import json
from urllib.parse import urljoin, urlparse


def search(driver):
    driver.get("http://www.python.org")
    assert "Python" in driver.title
    elem = driver.find_element_by_name("q")  # search on page, send another request
    elem.clear()
    elem.send_keys("pycon")  # input
    elem.send_keys(Keys.RETURN)  # enter
    print(driver.page_source)
    driver.close()


def robots_txt():
    robots = Robots.fetch('http://www.e-prostor.gov.si/robots.txt')
    print(robots)
    print(robots.allowed('http://www.e-prostor.gov.si/nc/', '*'))
    print(robots.allowed('http://www.e-prostor.gov.si/fileadmin/global/', '*'))
    print('Crawl-delay: ', robots.agent('*').delay)
    print(robots.sitemaps)
    print(robots.agent('my-user-agent').delay)

    robots = Robots.fetch('http://www.e-prostor.gov.si/robots.txt')
    print(robots)
    lst = list(robots.sitemaps)
    r = requests.get(lst[0])
    root = etree.fromstring(r.content)
    for sitemap in root:
        children = sitemap.getchildren()
        print(children[0].text)


def hash_function():
    a = "<html></html>"
    b = bytes("<html></html>", 'utf-8')
    m = hashlib.md5()
    m.update(b)
    hashed = m.digest()
    print(hashed)


def domain():
    import re
    r = re.compile(r"https?://(www\.)?")
    url = 'https://google.com/images'
    root_url = '{}://{}'.format(urlparse(url).scheme,
                                urlparse(url).netloc)
    domain = r.sub('', root_url).strip().strip('/')
    print(domain)


def filesize(url):
    file_base64 = base64.b64encode(requests.get(url).content)
    print((len(file_base64) * 3) / 4)


def firefox_setup():
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)
    driver.get("https://evem.gov.si")
    print(driver.page_source)
    driver.save_screenshot('data/firefox.png')
    driver.close()


def chrome_setup():
    options = webdriver.ChromeOptions()
    options.add_argument("headless")
    d = DesiredCapabilities.CHROME
    d['loggingPrefs'] = {'performance': 'ALL'}
    options.add_experimental_option("prefs", {"profile.default_content_settings.cookies": 2})  # disable cookies
    driver = webdriver.Chrome(options=options, desired_capabilities=d)
    driver.get("https://evem.gov.si")
    print(driver.page_source)
    performance_log = driver.get_log('performance')
    #print(str(performance_log).strip('[]'))
    for entry in driver.get_log('performance'):
        print(entry)
    driver.save_screenshot('data/chrome.png')
    driver.close()


def phantomjs_setup():
    driver = webdriver.PhantomJS()
    driver.get("https://evem.gov.si")
    print(driver.page_source)
    driver.save_screenshot('data/phantom.png')
    status_code = json.loads(driver.get_log('har')[0]['message'])['log']['entries'][0]['response']['status']
    #print(status_code)
    driver.close()


def insert_all(s):
    site = Site(
        domain='evem.gov.si',
        robots_content='Allow: /',
        sitemap_content='<html><p>hello</p></html>'
    )
    s.add(site)
    s.commit()
    site_id = site.id

    now = datetime.datetime.now().date()
    b = bytes("<html></html>", 'utf-8')
    m = hashlib.md5()
    m.update(b)
    hashed = m.digest()
    page = Page(
        site_id=site_id,
        page_type_code='HTML',
        url='https://www.rtvslo.si',  # UNIQUE
        html_content='<div>Hello</div>',
        http_status_code=200,
        accessed_time=now,
        hash=hashed
    )
    s.add(page)
    s.commit()
    page_id = page.id

    with open('data/chrome.png', "rb") as image_file:
        encoded = base64.b64encode(image_file.read())
    image = Image(
        page_id=page_id,
        filename='image.jpeg',
        content_type='JPEG',
        data=encoded,
        accessed_time=now
    )
    s.add(image)
    s.commit()

    page_data = PageData(
        page_id=page_id,
        data_type_code='PDF',
        data=encoded
    )
    s.add(page_data)
    s.commit()

    link = Link(
        from_page=page_id,
        to_page=page_id
    )
    s.add(link)
    s.commit()


def delete_all(s):
    s.query(Image).delete()
    s.commit()
    s.query(Link).delete()
    s.commit()
    s.query(PageData).delete()
    s.commit()
    s.query(Page).delete()
    s.commit()
    s.query(Site).delete()
    s.commit()


def select_all(s):
    stmt = s.query(Page)
    pages = stmt.all()
    if len(pages) > 0:
        hashes = [pages.hash for pages in pages]
        print(hashes)
        print(hashes[0] == hashes[1])


def uniqueness(s):
    stmt = s.query(Site).filter(Site.domain == 'evem.gov.si')
    site = stmt.first()
    if site is not None:
        site_id = site.id
        print(site_id)

        now = datetime.datetime.now().date()
        b = bytes("<div></div>", 'utf-8')
        m = hashlib.md5()
        m.update(b)
        hashed = m.digest()
        page = Page(
            site_id=site_id,
            page_type_code='HTML',
            url='https://www.najdi.si',  # UNIQUE
            html_content='<div>Goodbye</div>',
            http_status_code=200,
            accessed_time=now,
            hash=hashed
        )
        try:
            s.add(page)
            s.commit()
        except Exception as e:
            print(e)


# MAIN
# java -jar selenium-server-standalone-3.141.59.jar

#firefox_setup()
#chrome_setup()
#phantomjs_setup()

meta = MetaData(schema="crawldb")
Base = declarative_base(metadata=meta)
DATABASE_URI = 'postgres+psycopg2://postgres:rokzidarn@localhost:5432/crawldb'

engine = create_engine(DATABASE_URI)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

s = Session()

s.close()
