"""Weather service using Open-Meteo API (free, no API key required)."""
import json
from datetime import datetime, timedelta

import requests

# Major Chinese cities with coordinates
CITY_COORDS = {
    '上海市': {'lat': 31.23, 'lng': 121.47},
    '北京市': {'lat': 39.90, 'lng': 116.40},
    '广州市': {'lat': 23.13, 'lng': 113.26},
    '深圳市': {'lat': 22.54, 'lng': 114.06},
    '杭州市': {'lat': 30.27, 'lng': 120.15},
    '成都市': {'lat': 30.57, 'lng': 104.07},
    '武汉市': {'lat': 30.59, 'lng': 114.31},
    '南京市': {'lat': 32.06, 'lng': 118.80},
    '重庆市': {'lat': 29.56, 'lng': 106.55},
    '西安市': {'lat': 34.26, 'lng': 108.94},
    '苏州市': {'lat': 31.30, 'lng': 120.62},
    '天津市': {'lat': 39.13, 'lng': 117.20},
    '长沙市': {'lat': 28.23, 'lng': 112.94},
    '郑州市': {'lat': 34.75, 'lng': 113.65},
    '青岛市': {'lat': 36.07, 'lng': 120.38},
    '嘉兴市': {'lat': 30.75, 'lng': 120.76},
    '宁波市': {'lat': 29.87, 'lng': 121.55},
    '温州市': {'lat': 28.00, 'lng': 120.67},
    '合肥市': {'lat': 31.82, 'lng': 117.23},
    '福州市': {'lat': 26.07, 'lng': 119.30},
    '厦门市': {'lat': 24.48, 'lng': 118.09},
    '昆明市': {'lat': 25.04, 'lng': 102.68},
    '贵阳市': {'lat': 26.65, 'lng': 106.63},
    '南昌市': {'lat': 28.68, 'lng': 115.86},
    '济南市': {'lat': 36.65, 'lng': 116.99},
    '大连市': {'lat': 38.91, 'lng': 121.60},
    '哈尔滨市': {'lat': 45.75, 'lng': 126.65},
    '沈阳市': {'lat': 41.80, 'lng': 123.43},
    '长春市': {'lat': 43.88, 'lng': 125.32},
}


def get_weather(location='上海市', days=3):
    """Get weather data for the specified location.
    
    Args:
        location: City name (Chinese) or coordinates dict with 'lat' and 'lng'
        days: Number of days to fetch (1-7)
    
    Returns:
        dict with current weather and forecast, or None on error
    """
    # Get coordinates
    if isinstance(location, dict):
        lat = location.get('lat', 31.23)
        lng = location.get('lng', 121.47)
        city_name = location.get('name', '未知')
    else:
        coords = CITY_COORDS.get(location, CITY_COORDS.get('上海市'))
        lat = coords['lat']
        lng = coords['lng']
        city_name = location

    try:
        # Open-Meteo API - free, no key required
        url = 'https://api.open-meteo.com/v1/forecast'
        params = {
            'latitude': lat,
            'longitude': lng,
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max',
            'current_weather': True,
            'timezone': 'Asia/Shanghai',
            'forecast_days': min(days, 7),
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        result = {
            'city': city_name,
            'current': None,
            'forecast': [],
        }
        
        # Parse current weather
        current = data.get('current_weather', {})
        if current:
            result['current'] = {
                'temp': current.get('temperature'),
                'weather': _weather_code_to_desc(current.get('weathercode', 0)),
                'wind_speed': current.get('windspeed'),
            }
        
        # Parse daily forecast
        daily = data.get('daily', {})
        dates = daily.get('time', [])
        max_temps = daily.get('temperature_2m_max', [])
        min_temps = daily.get('temperature_2m_min', [])
        precip = daily.get('precipitation_sum', [])
        codes = daily.get('weathercode', [])
        wind = daily.get('windspeed_10m_max', [])
        
        for i in range(min(len(dates), days)):
            result['forecast'].append({
                'date': dates[i],
                'temp_max': max_temps[i] if i < len(max_temps) else None,
                'temp_min': min_temps[i] if i < len(min_temps) else None,
                'precipitation': precip[i] if i < len(precip) else None,
                'weather': _weather_code_to_desc(codes[i] if i < len(codes) else 0),
                'wind_speed': wind[i] if i < len(wind) else None,
            })
        
        return result
    except Exception as e:
        print(f'Weather fetch error: {e}')
        return None


def _weather_code_to_desc(code):
    """Convert WMO weather code to Chinese description."""
    weather_codes = {
        0: '晴',
        1: '大部晴朗',
        2: '局部多云',
        3: '多云',
        45: '雾',
        48: '雾凇',
        51: '小毛毛雨',
        53: '中毛毛雨',
        55: '大毛毛雨',
        56: '冻毛毛雨',
        57: '强冻毛毛雨',
        61: '小雨',
        63: '中雨',
        65: '大雨',
        66: '冻雨',
        67: '强冻雨',
        71: '小雪',
        73: '中雪',
        75: '大雪',
        77: '雪粒',
        80: '小阵雨',
        81: '中阵雨',
        82: '大阵雨',
        85: '小阵雪',
        86: '大阵雪',
        95: '雷暴',
        96: '雷暴伴小冰雹',
        99: '雷暴伴大冰雹',
    }
    return weather_codes.get(code, f'天气代码{code}')


def format_weather_for_chat(weather_data):
    """Format weather data for inclusion in chat context."""
    if not weather_data:
        return ''
    
    lines = [f'\n当前日期: {datetime.now().strftime("%Y-%m-%d")}']
    lines.append(f'所在城市: {weather_data["city"]}')
    
    current = weather_data.get('current')
    if current:
        lines.append(f'当前天气: {current["weather"]} {current["temp"]}°C')
    
    forecast = weather_data.get('forecast', [])
    if forecast:
        lines.append('近期天气预报:')
        for f in forecast:
            lines.append(f'  {f["date"]}: {f["weather"]}, {f["temp_min"]}~{f["temp_max"]}°C, 降水{f["precipitation"]}mm')
    
    return '\n'.join(lines)
