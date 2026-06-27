"""HTTP API 레이어 — 분석단/예측단 결과를 프론트(web/)가 소비할 JSON으로 노출.

기존 Python 모듈(report.builder / user_profile / demo_alert_runner)을 그대로
읽어 화면 모양으로 매핑한다. 새 분석 로직은 만들지 않는다(읽기/매핑 전용).
"""
