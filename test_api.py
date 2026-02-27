import requests
import json
from datetime import datetime, timedelta

# 测试新浪财经API
def test_sina_api(code):
    print(f"测试新浪财经API获取基金 {code} 数据...")
    try:
        fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(fund_url, headers=headers, timeout=5)
        print(f"新浪财经API响应状态: {response.status_code}")
        print(f"新浪财经API响应内容: {response.text[:200]}...")
        
        # 解析新浪财经的JS格式数据
        data_str = response.text.strip().replace('jsonpgz(', '').replace(');', '')
        data = json.loads(data_str)
        print(f"解析成功，基金名称: {data.get('name')}")
        return data
    except Exception as e:
        print(f"新浪财经API失败: {e}")
        return None

# 测试东方财富API
def test_eastmoney_api(code):
    print(f"测试东方财富API获取基金 {code} 历史数据...")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        fund_data_url = f"https://fundapi.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=100&startDate={start_date_str}&endDate={end_date_str}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(fund_data_url, headers=headers, timeout=5)
        print(f"东方财富API响应状态: {response.status_code}")
        
        data = response.json()
        print(f"解析成功，数据结构: {list(data.keys())}")
        if data.get('Data') and data['Data'].get('LSJZList'):
            print(f"获取到 {len(data['Data']['LSJZList'])} 条历史数据")
            print(f"第一条数据: {data['Data']['LSJZList'][0]}")
        return data
    except Exception as e:
        print(f"东方财富API失败: {e}")
        return None

# 测试函数
if __name__ == "__main__":
    fund_code = "001632"  # 测试基金代码
    print("=" * 50)
    test_sina_api(fund_code)
    print("=" * 50)
    test_eastmoney_api(fund_code)
    print("=" * 50)
