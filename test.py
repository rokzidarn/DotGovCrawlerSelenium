from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
import requests
from reppy.robots import Robots
import hashlib
from lxml import etree
import base64

def run_crawler(self):
    while len(self.url_queue):  # If we have URLs to crawl - we crawl
        current_url = self.url_queue.popleft()  # We grab a URL from the left of the list
        self.crawled_urls.append(current_url)  # We then add this URL to our crawled list
        html = self.get_page(current_url)
        if self.browser.current_url != current_url:
            self.crawled_urls.append(current_url)
        soup = self.get_soup(html)
        if soup is not None:  # If we have soup - parse and write to our csv file
            self.get_links(soup)
            title = self.get_data(soup)
            self.csv_output(current_url, title)


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
    options.add_experimental_option("prefs", {"profile.default_content_settings.cookies": 2})  # disable cookies
    driver = webdriver.Chrome(options=options)
    driver.get("https://evem.gov.si")
    print(driver.page_source)
    driver.save_screenshot('data/chrome.png')
    driver.close()

# MAIN
# java -jar selenium-server-standalone-3.141.59.jar

#firefox_setup()
chrome_setup()
