@echo off
cd /d "C:\Users\FC_임경민\Desktop\작업\정부 정책 스크래핑"
set PYTHONIOENCODING=utf-8
python policy_crawler.py >> run_log.txt 2>&1
