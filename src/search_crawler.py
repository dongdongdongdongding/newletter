from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
from database import Database
from datetime import datetime
import json

class BrunchCrawler:
    def __init__(self):
        """ChromeDriver를 초기화하고 브라우저 옵션을 설정합니다."""
        options = Options()
        options.add_argument('--headless')  # 헤드리스 모드
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.db = Database()
        
    def search(self, query, sort_by='recency'):
        """
        브런치 검색 결과를 크롤링합니다.
        
        Args:
            query (str): 검색어
            sort_by (str): 정렬 방식 ("recency" 또는 "accu")
            
        Returns:
            list: 검색 결과 목록. 각 항목은 딕셔너리 형태
                 {
                     "title": str,      # 글 제목
                     "content": str,    # 글 내용 미리보기
                     "url": str,        # 글 URL
                     "thumbnail": str,  # 썸네일 이미지 URL
                     "author": str,     # 작성자
                     "time": str,       # 작성 시간
                     "comments": str    # 댓글 수
                 }
        """
        url = f"https://brunch.co.kr/search?q={query}&type=article"
        if sort_by == "accu":
            url += "&sort=accu" 
            
        try:
            self.driver.get(url)
            time.sleep(2)  # 페이지 로딩 대기
            
            results = []
            articles = self.driver.find_elements(By.CSS_SELECTOR, "li[data-articleuid]")
            
            for article in articles:
                try:
                    # 제목
                    title = article.find_element(By.CSS_SELECTOR, ".tit_subject").text.strip()
                    
                    # URL
                    url = article.find_element(By.CSS_SELECTOR, "a.link_post").get_attribute("href")
                    
                    # 내용 미리보기
                    content = article.find_element(By.CSS_SELECTOR, ".article_content").text.strip()
                    
                    # 썸네일 (있는 경우만)
                    try:
                        thumbnail = article.find_element(By.CSS_SELECTOR, "img.img_thumb").get_attribute("src")
                    except:
                        thumbnail = None
                        
                    # 작성자
                    try:
                        author = article.find_element(By.CSS_SELECTOR, ".post_append span:last-child").text.strip()
                        if author.startswith("By "):
                            author = author[3:]
                    except:
                        author = "Unknown"
                        
                    # 작성 시간
                    try:
                        time_element = article.find_element(By.CSS_SELECTOR, ".publish_time")
                        time_text = time_element.text.strip()
                    except:
                        time_text = None
                        
                    # 댓글 수
                    try:
                        comments = article.find_element(By.CSS_SELECTOR, ".num_txt").text.strip()
                    except:
                        comments = "0"
                    
                    results.append({
                        "title": title,
                        "content": content,
                        "url": url,
                        "thumbnail": thumbnail,
                        "author": author,
                        "time": time_text,
                        "comments": comments
                    })
                    
                except Exception as e:
                    print(f"Error parsing article: {str(e)}")
                    continue
                    
            return results
            
        except Exception as e:
            print(f"Error in search: {str(e)}")
            return []
            
    def crawl_and_save_articles(self, article_urls):
        """
        주어진 URL들의 글을 크롤링하여 데이터베이스에 저장합니다.
        
        Args:
            article_urls (list): 크롤링할 글 URL 목록
        """
        for url in article_urls:
            try:
                # 이미 저장된 글인지 확인
                if self.db.get_article(url):
                    logging.info(f"이미 저장된 글입니다: {url}")
                    continue
                
                self.driver.get(url)
                time.sleep(2)  # 페이지 로딩 대기
                
                # 글 제목
                title = self.driver.find_element(By.CSS_SELECTOR, ".cover_title").text.strip()
                
                # 글 내용
                content_elements = self.driver.find_elements(By.CSS_SELECTOR, ".item_type_text")
                content = "\n".join([elem.text.strip() for elem in content_elements])
                
                # 작성자
                author = self.driver.find_element(By.CSS_SELECTOR, ".author_name").text.strip()
                
                # 썸네일 (있는 경우만)
                try:
                    thumbnail = self.driver.find_element(By.CSS_SELECTOR, ".cover_img").get_attribute("src")
                except:
                    thumbnail = None
                    
                # 도메인 정보
                domain = "brunch.co.kr"
                
                # 데이터베이스에 저장
                self.db.save_article({
                    "url": url,
                    "title": title,
                    "content": content,
                    "author": author,
                    "thumbnail": thumbnail,
                    "domain": domain,
                    "crawled_at": datetime.now()
                })
                
                logging.info(f"글을 저장했습니다: {title}")
                
            except Exception as e:
                logging.error(f"글 크롤링 중 오류 발생: {str(e)}")
                continue
                
    def close(self):
        """브라우저를 종료합니다."""
        try:
            self.driver.quit()
        except:
            pass
