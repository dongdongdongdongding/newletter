from flask import Flask, render_template, request, jsonify
from search_crawler import BrunchCrawler
from database import Database
import threading
import logging
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 데이터베이스 초기화
db = Database()
db.setup()

@app.route('/')
def index():
    return render_template('index.html', title="Newsletter App - Cloud Version")

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    sort_by = request.form.get('sort_by', 'recency')  # 기본값은 최신순
    
    if not query:
        return jsonify({'error': '검색어를 입력해주세요'})
        
    try:
        # 브런치 검색
        crawler = BrunchCrawler()
        results = crawler.search(query, sort_by)
        
        # 백그라운드에서 크롤링 및 저장 시작
        thread = threading.Thread(
            target=crawler.crawl_and_save_articles,
            args=([r['url'] for r in results],)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'results': results
        })
        
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {str(e)}")
        return jsonify({'error': '검색 중 오류가 발생했습니다'})

@app.route('/view_database')
def view_database():
    articles = db.get_all_articles()
    keywords = db.extract_keywords()
    return render_template('database.html', articles=articles, keywords=keywords)

@app.route('/extract_keywords', methods=['POST'])
def extract_keywords():
    try:
        keywords = db.extract_keywords()
        return jsonify({'keywords': keywords})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
