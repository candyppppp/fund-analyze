#!/usr/bin/env python3
# 测试股票名称解析

import requests
import re
import json


# 测试获取股票名称的函数
def test_get_stock_name():
    """测试从多个数据源获取股票名称"""
    test_codes = ["600519", "000858", "000333"]

    for stock_code in test_codes:
        print(f"\n测试股票代码: {stock_code}")

        # 数据源1: 新浪财经API
        print("\n尝试从新浪财经API获取股票名称...")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            # 对于沪市股票，需要添加sh前缀；深市股票添加sz前缀
            if stock_code.startswith('6'):
                full_code = f"sh{stock_code}"
            else:
                full_code = f"sz{stock_code}"

            stock_url = f"http://hq.sinajs.cn/list={full_code}"
            response = requests.get(stock_url, headers=headers, timeout=5)

            if response.status_code == 200:
                stock_data = response.text
                print(f"新浪财经API响应: {stock_data}")
                # 解析股票数据
                stock_info = stock_data.split(',')
                if len(stock_info) > 0:
                    # 提取股票名称
                    name_match = re.search(r'"(.*?)"', stock_info[0])
                    if name_match:
                        print(f"成功从新浪财经API获取股票名称: {name_match.group(1)}")
                        continue
            print("从新浪财经API获取股票名称失败")
        except Exception as e:
            print(f"从新浪财经API获取股票名称失败: {e}")


# 测试基金持仓数据获取
def test_fund_holdings():
    """测试获取基金持仓数据"""
    fund_code = "000001"
    print(f"\n测试基金代码: {fund_code}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # 尝试从东方财富获取基金持仓数据
    print("\n尝试从东方财富获取基金持仓数据...")
    try:
        fund_data_url = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
        response = requests.get(fund_data_url, headers=headers, timeout=10)

        if response.status_code == 200:
            data_str = response.text
            print(f"东方财富API响应状态: {response.status_code}")

            # 打印响应内容的前1000字符，以便调试
            print(f"响应内容前1000字符: {data_str[:1000]}")

            # 尝试提取 Data_holdStock 变量
            data_hold_stock_match = re.search(r'var Data_holdStock = $$(.*?)$$;', data_str, re.DOTALL)
            if data_hold_stock_match:
                data_hold_stock_str = data_hold_stock_match.group(1)
                try:
                    data_hold_stock = json.loads('[' + data_hold_stock_str + ']')
                    print(f"成功解析 Data_holdStock，共 {len(data_hold_stock)} 只股票")

                    for stock in data_hold_stock[:5]:  # 只显示前5只
                        try:
                            code = stock.get('code', '')
                            name = stock.get('name', '')
                            weight = stock.get('percent', 0) * 100  # 转换为百分比

                            if code and name:
                                print(f"股票: {name}, 代码: {code}, 权重: {weight}%")
                        except Exception as e:
                            print(f"解析股票数据失败: {e}")
                except Exception as e:
                    print(f"解析 Data_holdStock 失败: {e}")
            else:
                print("未找到 Data_holdStock 变量")

                # 尝试提取 stockCodes 变量
                stock_codes_match = re.search(r'var stockCodes\s*=\s*$$([^$$]*)\];', data_str)
                if stock_codes_match:
                    stock_codes_str = stock_codes_match.group(1)
                    try:
                        stock_codes = json.loads('[' + stock_codes_str + ']')
                        print(f"成功解析 stockCodes，共 {len(stock_codes)} 只股票")

                        # 尝试提取 stockNames 变量
                        stock_names_match = re.search(r'var stockNames\s*=\s*$$([^$$]*)\];', data_str)
                        stock_names = []
                        if stock_names_match:
                            try:
                                stock_names_str = stock_names_match.group(1)
                                stock_names = json.loads('[' + stock_names_str + ']')
                                print(f"成功解析 stockNames，共 {len(stock_names)} 个股票名称")

                                for i, code in enumerate(stock_codes[:5]):  # 只显示前5只
                                    if i < len(stock_names):
                                        print(f"股票: {stock_names[i]}, 代码: {code}")
                            except Exception as e:
                                print(f"解析 stockNames 失败: {e}")
                        else:
                            print("未找到 stockNames 变量")
                    except Exception as e:
                        print(f"解析 stockCodes 失败: {e}")
                        # 尝试提取 stockCodesNew 变量
                        stock_codes_new_match = re.search(r'var stockCodesNew\s*=\s*$$([^$$]*)\];', data_str)
                        if stock_codes_new_match:
                            stock_codes_new_str = stock_codes_new_match.group(1)
                            try:
                                stock_codes_new = json.loads('[' + stock_codes_new_str + ']')
                                print(f"成功解析 stockCodesNew，共 {len(stock_codes_new)} 只股票")

                                # 尝试提取 stockNamesNew 变量
                                stock_names_new_match = re.search(r'var stockNamesNew\s*=\s*$$([^$$]*)\];', data_str)
                                stock_names_new = []
                                if stock_names_new_match:
                                    try:
                                        stock_names_new_str = stock_names_new_match.group(1)
                                        stock_names_new = json.loads('[' + stock_names_new_str + ']')
                                        print(f"成功解析 stockNamesNew，共 {len(stock_names_new)} 个股票名称")

                                        for i, code_str in enumerate(stock_codes_new[:5]):  # 只显示前5只
                                            if i < len(stock_names_new):
                                                print(f"股票: {stock_names_new[i]}, 代码: {code_str}")
                                    except Exception as e:
                                        print(f"解析 stockNamesNew 失败: {e}")
                                else:
                                    print("未找到 stockNamesNew 变量")
                            except Exception as e2:
                                print(f"解析 stockCodesNew 失败: {e2}")
                else:
                    print("未找到 stockCodes 变量")
    except Exception as e:
        print(f"从东方财富获取基金持仓数据失败: {e}")


if __name__ == "__main__":
    # 测试股票名称解析
    test_get_stock_name()

    # 测试基金持仓数据获取
    test_fund_holdings()