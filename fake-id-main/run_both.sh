#!/bin/bash
cd fake-id-main
echo "✅ 웹사이트 시작..."
python web.py &
echo "✅ 디스코드 봇 시작..."
python index.py &
wait
