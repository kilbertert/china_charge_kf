.PHONY: test install clean

install:
	pip install -r requirements.txt

test:
	python3 -m pytest tests/ -v
	# 或直接运行:
	python3 tests/test_csv_parser.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# 快速使用
menu:
	python3 structurer.py csv-to-menu \
		--input 32-6.17（充电桩知识库）/data_processed.csv \
		--output /tmp/menu_docs/

upload-menu:
	python3 structurer.py upload-to-dify \
		--kb-id c1b76f43-6110-4ee1-9cd9-1bcbb8c06220 \
		--md-dir /tmp/menu_docs/

all: install test