import json
import os
import pytest
from src.analyzer import calculate_velocity, calculate_engagement_rate, get_top_trends

def load_mock_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, 'mock_data.json')
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_calculate_velocity():
    assert calculate_velocity(1000, 1500) == 500
    assert calculate_velocity(5000, 5000) == 0

def test_calculate_engagement_rate():
    # 50 likes, 10 comments, 5 shares, 1000 views => (65/1000)*100 = 6.5
    rate = calculate_engagement_rate(50, 10, 5, 1000)
    assert rate == 6.5
    
    # zero views
    assert calculate_engagement_rate(50, 10, 5, 0) == 0.0

def test_get_top_trends():
    data = load_mock_data()
    t1 = data['t1']
    t2 = data['t2']
    
    trends = get_top_trends(t1, t2, top_n=3)
    
    assert len(trends) == 3
    # v3 velocity: 4000 - 800 = 3200
    # v4 velocity: 16000 - 15000 = 1000
    # v1 velocity: 1500 - 1000 = 500
    # v2 velocity: 5500 - 5000 = 500
    
    assert trends[0]['id'] == 'v3'
    assert trends[0]['velocity'] == 3200
    assert trends[1]['id'] == 'v4'
    assert trends[1]['velocity'] == 1000
    assert trends[2]['velocity'] == 500
