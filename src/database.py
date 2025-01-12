import sqlite3
import os
from datetime import datetime
import re
from collections import Counter

class Database:
    def __init__(self, db_path='newsletter.db'):
        self.db_path = db_path
        
    def setup(self):
        """데이터베이스와 테이블을 생성합니다."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # articles 테이블 생성
        c.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT,
                author TEXT,
                thumbnail TEXT,
                crawled_at DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def save_article(self, article):
        """글을 데이터베이스에 저장합니다."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT OR REPLACE INTO articles 
                (url, title, content, author, thumbnail, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                article['url'],
                article['title'],
                article['content'],
                article['author'],
                article.get('thumbnail'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            
        except Exception as e:
            print(f"Error saving article: {str(e)}")
            conn.rollback()
            
        finally:
            conn.close()
            
    def get_all_articles(self):
        """저장된 모든 글을 가져옵니다."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT url, title, content, author, thumbnail, crawled_at
            FROM articles
            ORDER BY crawled_at DESC
        ''')
        
        articles = []
        for row in c.fetchall():
            articles.append({
                'url': row[0],
                'title': row[1],
                'content': row[2],
                'author': row[3],
                'thumbnail': row[4],
                'crawled_at': row[5]
            })
            
        conn.close()
        return articles
        
    def get_article(self, url):
        """URL로 글을 조회합니다."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT * FROM articles WHERE url = ?', (url,))
        article = c.fetchone()
        
        conn.close()
        return article
        
    def extract_keywords(self):
        """모든 글의 내용에서 상위 30개 키워드를 추출합니다."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 모든 글의 내용을 가져옴
        c.execute('SELECT content FROM articles')
        contents = [row[0] for row in c.fetchall()]
        conn.close()
        
        # 불용어 목록
        stop_words = {
            '있습니다', '있는', '있다', '그리고', '그런데', '하지만', '입니다', '이런', 
            '저런', '그런', '이렇게', '저렇게', '그렇게', '때문에', '이것', '저것', '그것',
            '이번', '저번', '이후', '이전', '통해', '따라', '위해', '라고', '이라고',
            '하는', '한다', '됩니다', '된다'
        }
        
        # 한글 단어 추출 (2글자 이상)
        words = []
        for content in contents:
            if content:
                # 문장 단위로 분리
                sentences = re.split(r'[.!?]\s+', content)
                for sentence in sentences:
                    # 조사를 제외한 명사 추출 시도
                    # 1. 조사 패턴
                    patterns = [
                        r'[가-힣]{2,}(?=[은는이가을를에의로])',  # 조사 앞의 단어
                        r'[가-힣]{2,}(?=[^가-힣]|$)'  # 문장 끝이나 한글이 아닌 문자 앞의 단어
                    ]
                    
                    for pattern in patterns:
                        found_words = re.findall(pattern, sentence)
                        words.extend([w for w in found_words if len(w) >= 2 and w not in stop_words])
        
        # 상위 30개 키워드 추출
        counter = Counter(words)
        keywords = counter.most_common(30)
        
        return keywords
