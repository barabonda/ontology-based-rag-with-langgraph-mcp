"""
날씨 정보를 제공하는 MCP 서버 예제
------------------------------
이 파일은 SSE 전송 방식을 사용하는 날씨 정보 MCP 서버입니다.

실행 방법: python weather_server.py
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")

@mcp.tool()
def get_weather(location: str) -> str:
    """지정된 위치의 날씨 정보를 반환합니다."""
    weather_data = {
        "nyc": "뉴욕: 맑음, 22°C",
        "seoul": "서울: 흐림, 18°C",
        "london": "런던: 비, 15°C",
        "tokyo": "도쿄: 맑음, 24°C",
        "paris": "파리: 구름 조금, 20°C"
    }
    
    # 위치를 소문자로 변환하여 검색
    location_lower = location.lower()
    
    # 정확한 도시 이름이 없는 경우 부분 일치 확인
    if location_lower in weather_data:
        return weather_data[location_lower]
    
    # 부분 일치 확인
    for city, weather in weather_data.items():
        if city in location_lower or location_lower in city:
            return weather_data[city]
    
    return f"{location}의 날씨 정보를 찾을 수 없습니다."

if __name__ == "__main__":
    print("Weather MCP 서버 시작 중 (포트 8000)...")
    print("다른 터미널에서 MCP 클라이언트를 사용하여 이 서버에 연결하세요.")
    mcp.run(transport="sse", port=8000) 