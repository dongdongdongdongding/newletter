from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import chromedriver_autoinstaller
from datetime import datetime
import sqlite3
import os
import logging
import re
import urllib.parse

class WebCrawler:
    def __init__(self):
        # SQLite 데이터베이스 연결
        self.db_path = 'brunch_articles.db'
        self.conn = sqlite3.connect(self.db_path)
        self.create_tables()
        
        # ChromeDriver 자동 설치
        chromedriver_autoinstaller.install()
        
        # Chrome 옵션 설정
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            print(f"Chrome driver 초기화 오류: {str(e)}")
            raise

    def create_tables(self):
        """데이터베이스 테이블을 생성합니다."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT,
                domain TEXT,
                crawled_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def wait_for_element(self, selector, timeout=10):
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element
        except Exception as e:
            logging.error(f"Element not found: {selector}")
            return None

    def scroll_to_bottom(self):
        SCROLL_PAUSE_TIME = 1
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)
            
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def clean_text(self, text):
        if not text:
            return ""
        # 연속된 공백 제거
        text = re.sub(r'\s+', ' ', text)
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        # 앞뒤 공백 제거
        return text.strip()

    def extract_brunch_content(self, soup):
        content_parts = []
        
        # 1. 커버 섹션 처리
        cover = soup.select_one('.wrap_cover')
        if cover:
            # 제목
            title_elem = cover.select_one('h1.cover_title')
            if title_elem:
                content_parts.append(f"제목: {self.clean_text(title_elem.text)}\n")
            
            # 부제목
            subtitle_elem = cover.select_one('p.cover_sub_title')
            if subtitle_elem:
                content_parts.append(f"부제: {self.clean_text(subtitle_elem.text)}\n")
            
            # 작성자 정보
            author_elem = cover.select_one('#wrapArticleInfo .text_author a')
            if author_elem:
                content_parts.append(f"작성자: {self.clean_text(author_elem.text)}")
            
            # 작성일
            date_elem = cover.select_one('#wrapArticleInfo .date')
            if date_elem:
                content_parts.append(f"작성일: {self.clean_text(date_elem.text)}")
            
            content_parts.append("\n" + "="*50 + "\n")  # 구분선
        
        # 2. 본문 섹션 처리
        body = soup.select_one('.wrap_body')
        if body:
            # 모든 콘텐츠 아이템 처리
            items = body.select('.wrap_item')
            for item in items:
                # 텍스트 아이템
                if 'item_type_text' in item.get('class', []):
                    # 제목 (h1~h6)
                    if item.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        text = self.clean_text(item.text)
                        if text:
                            content_parts.append(f"\n## {text}\n")
                    else:
                        text = self.clean_text(item.text)
                        if text:
                            content_parts.append(text + "\n")
                
                # 이미지 아이템
                elif 'item_type_img' in item.get('class', []):
                    img = item.select_one('img')
                    if img:
                        img_url = img.get('src', '')
                        if img_url:
                            if not img_url.startswith('http'):
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                else:
                                    img_url = urllib.parse.urljoin('https://brunch.co.kr', img_url)
                            content_parts.append(f"\n[이미지: {img_url}]\n")
                    
                    # 이미지 캡션
                    caption = item.select_one('.text_caption')
                    if caption:
                        caption_text = self.clean_text(caption.text)
                        if caption_text:
                            content_parts.append(f"[이미지 설명: {caption_text}]\n")
                
                # 인용구 아이템
                elif 'item_type_quote' in item.get('class', []):
                    quote = self.clean_text(item.text)
                    if quote:
                        content_parts.append(f"\n> {quote}\n")
                
                # 구분선
                elif 'item_type_hr' in item.get('class', []):
                    content_parts.append("\n---\n")
        
        return "\n".join(content_parts)

    def crawl(self, url):
        try:
            self.driver.get(url)
            
            if 'brunch.co.kr' in url:
                # 브런치 페이지가 완전히 로드될 때까지 대기
                main_content = self.wait_for_element('.wrap_article')
                if not main_content:
                    raise Exception("메인 콘텐츠를 찾을 수 없습니다")
                
                # 전체 콘텐츠가 로드되도록 스크롤
                self.scroll_to_bottom()
                time.sleep(2)  # 추가 대기 시간
                
                html = self.driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                # 브런치 전용 콘텐츠 추출
                content = self.extract_brunch_content(soup)
                
                # 제목은 별도로 추출 (메타데이터용)
                title_elem = soup.select_one('h1.cover_title')
                title = self.clean_text(title_elem.text) if title_elem else 'No Title'
            
            article_data = {
                'url': url,
                'title': title.strip() if title else 'No Title',
                'content': content.strip(),
                'domain': urllib.parse.urlparse(url).netloc,
                'crawled_at': datetime.now()
            }
            
            return article_data
            
        except Exception as e:
            logging.error(f"크롤링 중 오류 발생: {str(e)}")
            raise Exception(f"크롤링 중 오류 발생: {str(e)}")

    def save_to_db(self, article_data):
        """크롤링한 글을 SQLite 데이터베이스에 저장합니다."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO articles 
                (url, title, content, domain, crawled_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                article_data['url'],
                article_data['title'],
                article_data['content'],
                article_data['domain'],
                article_data['crawled_at']
            ))
            self.conn.commit()
            print(f"저장 완료: {article_data['title']}")
            
        except Exception as e:
            print(f"데이터베이스 저장 중 오류: {str(e)}")
            raise

    def close(self):
        """브라우저와 데이터베이스 연결을 종료합니다."""
        try:
            self.driver.quit()
            self.conn.close()
        except Exception as e:
            print(f"리소스 정리 중 오류: {str(e)}")
