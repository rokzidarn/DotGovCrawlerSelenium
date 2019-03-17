from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, MetaData, Column, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, query
from sqlalchemy.dialects.mysql import TEXT, VARCHAR, INTEGER, TIMESTAMP, LONGBLOB, CHAR

# https://learndatasci.com/tutorials/using-databases-python-postgres-sqlalchemy-and-alembic/
# https://www.pythonsheets.com/notes/python-sqlalchemy.html

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
    data = Column(LONGBLOB, nullable=False)
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


class Link(Base):
    __tablename__ = "link"

    from_page = Column(INTEGER, primary_key=True, nullable=False)
    to_page = Column(INTEGER, primary_key=True, nullable=False)
