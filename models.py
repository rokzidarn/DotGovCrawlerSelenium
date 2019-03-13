from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, MetaData, Column, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.mysql import TEXT, VARCHAR, INTEGER, TIMESTAMP, LONGBLOB, CHAR
import datetime
import base64
import hashlib

# https://learndatasci.com/tutorials/using-databases-python-postgres-sqlalchemy-and-alembic/

meta = MetaData(schema="crawldb")
Base = declarative_base(metadata=meta)
DATABASE_URI = 'postgres+psycopg2://postgres:rokzidarn@localhost:5432/crawldb'


class Site(Base):
    __tablename__ = "site"

    id = Column(INTEGER, primary_key=True, nullable=False)
    domain = Column(VARCHAR(500))
    robots_content = Column(TEXT)
    sitemap_content = Column(TEXT)
    pages = relationship("Page")


class Page(Base):
    __tablename__ = "page"

    id = Column(INTEGER, primary_key=True, nullable=False)
    site_id = Column(INTEGER, ForeignKey('site.id'))
    page_type_code = Column(VARCHAR(20), ForeignKey('page_type.code'))
    url = Column(VARCHAR(3000), unique=True)
    html_content = Column(TEXT)
    http_status_code = Column(INTEGER)
    accessed_time = Column(TIMESTAMP)
    hash = Column(CHAR(64))  # md5 hash value of HTML
    images = relationship("Image")
    page_datas = relationship("PageData")


class Image(Base):
    __tablename__ = "image"

    id = Column(INTEGER, primary_key=True, nullable=False)
    page_id = Column(INTEGER, ForeignKey('page.id'))
    filename = Column(VARCHAR(255))
    content_type = Column(VARCHAR(50))
    data = Column(LONGBLOB, nullable=False)  # TODO: bytea datatype in DB
    accessed_time = Column(TIMESTAMP)


class PageData(Base):
    __tablename__ = "page_data"

    id = Column(INTEGER, primary_key=True, nullable=False)
    page_id = Column(INTEGER, ForeignKey('page.id'))
    data_type_code = Column(VARCHAR(20), ForeignKey('data_type.code'))
    data = Column(LONGBLOB)


class DataType(Base):
    __tablename__ = "data_type"

    code = Column(VARCHAR(20), primary_key=True, nullable=False)  # PDF, DOC, DOCX, PPT, PPTX
    page_datas = relationship("PageData")


class PageType(Base):
    __tablename__ = "page_type"

    code = Column(VARCHAR(20), primary_key=True, nullable=False)  # HTML, BINARY, DUPLICATE, FRONTIER
    pages = relationship("Page")


class Link(Base):  # TODO: Link table - composite primary key
    __tablename__ = "link"

    from_page = Column(INTEGER, primary_key=True, nullable=False)
    to_page = Column(INTEGER, primary_key=True, nullable=False)


def insert_test(s):
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
        url='https://www.rtvslo.si',
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


# MAIN

engine = create_engine(DATABASE_URI)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

s = Session()
insert_test(s)
s.close()
