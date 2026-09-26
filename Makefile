.PHONY: up down check-db run

up:
	docker-compose up -d

down:
	docker-compose down

check-db:
	python scripts/check_db.py

run:
	python portal/app.py
