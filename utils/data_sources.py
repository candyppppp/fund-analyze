import requests
import json
import re
import time
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)


class DataSourceManager:
    """数据源管理类，用于管理不同的数据源"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
        # 禁用代理
        self.proxies = {
            'http': None,
            'https': None
        }
        # 数据源配置（按优先级排列，优先用数据量大、格式稳定的源）
        self.data_sources = {
            'latest_nav': ['sina', 'eastmoney'],
            'historical_data': ['eastmoney', '天天基金', '蛋卷基金', '好买基金', '天天基金移动端'],
            'holdings': ['eastmoney', '天天基金'],
            'estimated_return': ['sina', 'eastmoney'],
        }
        # 数据源健康状态
        self.source_health = {
            'sina': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
            'eastmoney': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
            '天天基金': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
            '蛋卷基金': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
            '好买基金': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
            '天天基金移动端': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
        }
        # 数据源健康检查阈值
        self.health_threshold = 3  # 连续失败次数阈值
        self.retry_interval = 60  # 数据源恢复检查间隔（秒）

    def get_fund_latest_nav(self, code):
        """获取基金最新净值（多数据源）"""
        data_list = []

        # 尝试从不同数据源获取数据
        for source in self.data_sources['latest_nav']:
            if not self._is_source_available(source):
                logger.warning(f"数据源 {source} 不可用，跳过")
                continue

            if source == 'sina':
                result = self._get_fund_latest_nav_sina(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从新浪财经获取基金 {code} 最新净值成功")
            elif source == 'eastmoney':
                result = self._get_fund_latest_nav_eastmoney(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从东方财富获取基金 {code} 最新净值成功")
            elif source == '同花顺':
                result = self._get_fund_latest_nav_ths(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从同花顺获取基金 {code} 最新净值成功")
            elif source == '聚宽':
                result = self._get_fund_latest_nav_joinquant(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从聚宽获取基金 {code} 最新净值成功")

        # 验证数据一致性并选择最佳数据
        best_data = self.validate_data_consistency('latest_nav', data_list)
        if best_data:
            logger.info(f"选择最佳数据源: {best_data.get('source', '未知')}")
            return best_data

        logger.error(f"所有数据源获取基金 {code} 最新净值失败")
        return None

    def _get_fund_latest_nav_sina(self, code):
        """获取基金最新净值（新浪财经API）"""
        try:
            fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            response = requests.get(fund_url, headers=self.headers, timeout=3, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                data_str = response.text.strip().replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)
                return {
                    'name': data.get('name', f'基金{code}'),
                    'jzrq': data.get('jzrq'),
                    'dwjz': float(data.get('dwjz', 0)),
                    'gsz': float(data.get('gsz', 0)),
                    'gszzl': float(data.get('gszzl', 0)) / 100,
                    'gztime': data.get('gztime'),
                    'source': '新浪财经'
                }
        except Exception as e:
            logger.error(f"从新浪财经获取基金最新净值失败: {e}")
        return None

    def _get_fund_latest_nav_eastmoney(self, code):
        """获取基金最新净值（东方财富API）"""
        try:
            fund_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
            response = requests.get(fund_url, headers=self.headers, timeout=3, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                data_str = response.text
                # 提取基金基本信息
                name_match = re.search(r'var fund_name = "(.*?)";', data_str)
                jzrq_match = re.search(r'var Data_1y = \[(.*?)\];', data_str)
                dwjz_match = re.search(r'var Data_netWorthTrend = \[(.*?)\];', data_str)

                name = name_match.group(1) if name_match else f'基金{code}'

                # 提取最新净值和日期
                if dwjz_match:
                    networth_data = dwjz_match.group(1)
                    # 解析净值数据
                    networth_list = re.findall(r'\{.*?\}', networth_data)
                    if networth_list:
                        latest_data = networth_list[-1]
                        date_match = re.search(r'date":"(.*?)"', latest_data)
                        value_match = re.search(r'value":(.*?),', latest_data)
                        if date_match and value_match:
                            date_str = date_match.group(1)
                            nav = float(value_match.group(1))
                            return {
                                'name': name,
                                'jzrq': date_str,
                                'dwjz': nav,
                                'gsz': nav,  # 东方财富API可能没有实时估值
                                'gszzl': 0,  # 东方财富API可能没有实时估值
                                'gztime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                'source': '东方财富'
                            }
        except Exception as e:
            logger.error(f"从东方财富获取基金最新净值失败: {e}")
        return None

    def _get_fund_latest_nav_ths(self, code):
        """获取基金最新净值（同花顺API）"""
        try:
            fund_url = f"http://fund.10jqka.com.cn/{code}/"
            response = requests.get(fund_url, headers=self.headers, timeout=5, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 提取基金名称
                name_match = re.search(r'<h1 class="fund_name">(.*?)</h1>', response.text)
                # 提取最新净值
                nav_match = re.search(r'<span class="fundNAV">(.*?)</span>', response.text)
                # 提取日期
                date_match = re.search(r'<span class="fundDate">(.*?)</span>', response.text)

                if name_match and nav_match and date_match:
                    name = name_match.group(1).strip()
                    nav = float(nav_match.group(1))
                    date_str = date_match.group(1).strip()

                    return {
                        'name': name,
                        'jzrq': date_str,
                        'dwjz': nav,
                        'gsz': nav,
                        'gszzl': 0,
                        'gztime': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'source': '同花顺'
                    }
        except Exception as e:
            logger.error(f"从同花顺获取基金最新净值失败: {e}")
        return None

    def _get_fund_latest_nav_joinquant(self, code):
        """获取基金最新净值（聚宽API）"""
        try:
            # 聚宽API需要API Key，这里使用公开数据
            fund_url = f"https://www.joinquant.com/query?code={code}"
            response = requests.get(fund_url, headers=self.headers, timeout=5, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 简单的解析，实际需要根据聚宽API返回格式调整
                # 注意：不使用模拟数据，只返回真实获取的数据
                # 由于聚宽API需要API Key，这里暂时返回None
                # 实际使用时需要根据具体API格式进行解析
                pass
        except Exception as e:
            logger.error(f"从聚宽获取基金最新净值失败: {e}")
        return None

    def get_fund_historical_data(self, code):
        """获取基金历史净值数据（多数据源）"""
        data_list = []

        # 尝试从不同数据源获取数据
        for source in self.data_sources['historical_data']:
            if not self._is_source_available(source):
                logger.warning(f"数据源 {source} 不可用，跳过")
                continue

            _func_map = {
                'eastmoney': self._get_fund_historical_data_eastmoney,
                '天天基金': self._get_fund_historical_data_tiantian,
                'sina': self._get_fund_historical_data_sina,
                '蛋卷基金': self._get_fund_historical_data_danjuan,
                '好买基金': self._get_fund_historical_data_howbuy,
                '天天基金移动端': self._get_fund_historical_data_tiantian_mobile,
            }
            func = _func_map.get(source)
            if func:
                result = func(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从 {source} 获取基金 {code} 历史数据成功，"
                                f"共 {len(result.get('prices', []))} 条")

        # 验证数据一致性并选择最佳数据
        best_data = self.validate_data_consistency('historical_data', data_list)
        if best_data:
            logger.info(f"选择最佳数据源: {best_data.get('source', '未知')}")
            return best_data

        logger.error(f"所有数据源获取基金 {code} 历史数据失败")
        return None

    def _get_fund_historical_data_eastmoney(self, code):
        """获取基金历史净值数据（东方财富 F10DataApi 接口）

        策略：
          1. 先拉第 1 页，从响应的 records 字段得到总记录数
          2. 根据实际每页条数计算总页数，再依次拉取剩余页
          3. 当某页无数据时提前退出，避免无效请求
        """
        try:
            all_prices = []
            all_dates = []

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": f"http://fund.eastmoney.com/{code}.html",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            def fetch_page(page, per=20):
                """拉取一页，返回 (dates, prices, total_records, per_page_actual)"""
                url = (f"http://fund.eastmoney.com/f10/F10DataApi.aspx"
                       f"?type=lsjz&code={code}&page={page}&per={per}")
                resp = requests.get(url, headers=headers, timeout=8, proxies=self.proxies)
                if resp.status_code != 200:
                    return [], [], 0, per

                text = resp.text

                # 从响应里读总记录数（接口会返回 records:XXXX）
                total = 0
                m_rec = re.search(r'records:(\d+)', text)
                if m_rec:
                    total = int(m_rec.group(1))

                # 提取表格
                m_table = re.search(r'(<table[^>]*>.*?</table>)', text, re.DOTALL)
                if not m_table:
                    return [], [], total, per

                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', m_table.group(1), re.DOTALL)
                page_dates, page_prices = [], []
                for row in rows[1:]:  # 跳过表头
                    cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                    cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
                    if len(cols) >= 2 and re.match(r'\d{4}-\d{2}-\d{2}', cols[0]):
                        try:
                            page_dates.append(cols[0])
                            page_prices.append(float(cols[1]))
                        except ValueError:
                            pass

                return page_dates, page_prices, total, len(page_dates)

            # 第 1 页：探测实际每页条数和总记录数
            d1, p1, total_records, actual_per = fetch_page(1, per=50)
            all_dates.extend(d1)
            all_prices.extend(p1)
            logger.info(f"东方财富 {code} 第1页: {len(d1)} 条，"
                        f"总记录数={total_records}，实际每页={actual_per}")

            if actual_per == 0:
                logger.warning(f"东方财富 {code} 第1页无数据")
                return None

            # 计算剩余页数（最多拉 3 年约 750 个交易日）
            max_records = 60
            if total_records > 0:
                total_pages = min((total_records + actual_per - 1) // actual_per,
                                  (max_records + actual_per - 1) // actual_per)
            else:
                total_pages = max_records // actual_per

            for page in range(2, total_pages + 1):
                d, p, _, cnt = fetch_page(page, per=actual_per)
                if cnt == 0:
                    logger.info(f"东方财富 {code} 第{page}页无数据，停止")
                    break
                all_dates.extend(d)
                all_prices.extend(p)
                logger.info(f"东方财富 {code} 第{page}页: {cnt} 条，已累计 {len(all_dates)} 条")
                if len(all_dates) >= max_records:
                    break

            if not all_dates:
                return None

            # 去重 + 排序
            unique = dict(zip(all_dates, all_prices))
            sorted_dates = sorted(unique.keys())
            sorted_prices = [unique[d] for d in sorted_dates]

            returns = [0]
            for i in range(1, len(sorted_prices)):
                try:
                    returns.append((sorted_prices[i] - sorted_prices[i - 1]) / sorted_prices[i - 1])
                except (ZeroDivisionError, TypeError):
                    returns.append(0)

            logger.info(f"东方财富共获取 {code} {len(sorted_prices)} 个数据点"
                        f"（{sorted_dates[0]} ~ {sorted_dates[-1]}）")
            return {'prices': sorted_prices, 'dates': sorted_dates,
                    'returns': returns, 'source': '东方财富'}
        except Exception as e:
            logger.error(f"从东方财富获取基金历史数据失败: {e}")
        return None

    def _get_fund_historical_data_tiantian(self, code):
        """天天基金历史净值（与东方财富同接口，直接复用 eastmoney 实现）"""
        result = self._get_fund_historical_data_eastmoney(code)
        if result:
            result['source'] = '天天基金'
        return result

    def _get_fund_historical_data_sina(self, code):
        """获取基金历史净值数据（新浪财经API）"""
        try:
            # 首先获取最新净值数据
            fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            response = requests.get(fund_url, headers=self.headers, timeout=5, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 解析新浪财经返回的数据
                data_str = response.text.strip().replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)

                # 构建历史数据
                prices = []
                dates = []
                returns = []

                # 添加最新数据
                if data.get('jzrq') and data.get('dwjz'):
                    dates.append(data['jzrq'])
                    prices.append(float(data['dwjz']))

                # 尝试从新浪财经的历史数据API获取更多数据
                # 新浪财经历史数据API
                history_url = f"http://finance.sina.com.cn/fund/quotes/{code}/history.shtml"
                response_history = requests.get(history_url, headers=self.headers, timeout=5, proxies=self.proxies)

                if response_history.status_code == 200:
                    # 尝试解析历史数据页面
                    # 这里使用简单的正则表达式提取数据
                    # 注意：这种方法可能会因为页面结构变化而失效
                    import re
                    # 尝试匹配历史净值数据
                    nav_pattern = re.compile(r'([0-9]{4}-[0-9]{2}-[0-9]{2})[^0-9]*([0-9]+\.[0-9]+)', re.DOTALL)
                    matches = nav_pattern.findall(response_history.text)

                    # 处理匹配到的数据
                    history_data = {}
                    for date_str, nav_str in matches:
                        try:
                            nav = float(nav_str)
                            history_data[date_str] = nav
                        except ValueError:
                            pass

                    # 将历史数据添加到列表中
                    for date_str, nav in sorted(history_data.items()):
                        if date_str not in dates:
                            dates.append(date_str)
                            prices.append(nav)

                # 计算收益率
                if len(prices) > 1:
                    for i in range(1, len(prices)):
                        try:
                            daily_return = (prices[i] - prices[i - 1]) / prices[i - 1]
                            returns.append(daily_return)
                        except (ZeroDivisionError, TypeError):
                            returns.append(0)
                    returns.insert(0, 0)

                # 即使只有一条数据，也返回，确保至少有最新净值
                if len(prices) > 0:
                    logger.info(f"新浪财经API返回了 {len(prices)} 个历史数据点")
                    return {
                        'prices': prices,
                        'dates': dates,
                        'returns': returns,
                        'source': '新浪财经'
                    }
        except Exception as e:
            logger.error(f"从新浪财经获取基金历史数据失败: {e}")
        return None

    def _get_fund_historical_data_danjuan(self, code):
        """获取基金历史净值数据（蛋卷基金 API）

        接口：https://danjuanfunds.com/djapi/fund/nav/history/{code}
        返回 JSON，items 字段包含历史净值列表，单次最多返回约 500 条。
        支持 page / size 分页参数，每页最多 500 条，拉取 2 页约 1000 条覆盖 3~4 年。
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://danjuanfunds.com/",
                "Accept": "application/json",
            }
            all_dates, all_prices = [], []

            for page in range(1, 3):  # 最多2页，每页500条，合计约1000条
                url = (f"https://danjuanfunds.com/djapi/fund/nav/history/{code}"
                       f"?page={page}&size=500")
                resp = requests.get(url, headers=headers, timeout=8, proxies=self.proxies)
                if resp.status_code != 200:
                    logger.warning(f"蛋卷基金 {code} 第{page}页 HTTP {resp.status_code}")
                    break

                data = resp.json()
                items = data.get("data", {}).get("items", [])
                if not items:
                    logger.info(f"蛋卷基金 {code} 第{page}页无数据，停止")
                    break

                for item in items:
                    date_str = item.get("date", "")
                    nav_str = item.get("nav", "") or item.get("unit_nav", "")
                    if not date_str or not nav_str:
                        continue
                    if not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                        continue
                    try:
                        all_dates.append(date_str)
                        all_prices.append(float(nav_str))
                    except ValueError:
                        pass

                logger.info(f"蛋卷基金 {code} 第{page}页: {len(items)} 条，已累计 {len(all_dates)} 条")

            if not all_dates:
                return None

            unique = dict(zip(all_dates, all_prices))
            sorted_dates = sorted(unique.keys())
            sorted_prices = [unique[d] for d in sorted_dates]

            returns = [0]
            for i in range(1, len(sorted_prices)):
                try:
                    returns.append((sorted_prices[i] - sorted_prices[i - 1]) / sorted_prices[i - 1])
                except (ZeroDivisionError, TypeError):
                    returns.append(0)

            logger.info(f"蛋卷基金共获取 {code} {len(sorted_prices)} 个数据点"
                        f"（{sorted_dates[0]} ~ {sorted_dates[-1]}）")
            return {"prices": sorted_prices, "dates": sorted_dates,
                    "returns": returns, "source": "蛋卷基金"}
        except Exception as e:
            logger.error(f"从蛋卷基金获取历史数据失败: {e}")
        return None

    def _get_fund_historical_data_howbuy(self, code):
        """获取基金历史净值数据（好买基金 API）

        接口：https://www.howbuy.com/fund/ajax/jzzsList.htm
        参数：jjdm=基金代码，返回 JSON，data 字段包含净值列表。
        无分页，单次返回全部历史数据（通常 3~5 年），是较好的补充源。
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": f"https://www.howbuy.com/fund/{code}/",
                "Accept": "application/json, text/javascript, */*",
                "X-Requested-With": "XMLHttpRequest",
            }
            url = f"https://www.howbuy.com/fund/ajax/jzzsList.htm?jjdm={code}"
            resp = requests.get(url, headers=headers, timeout=10, proxies=self.proxies)
            if resp.status_code != 200:
                logger.warning(f"好买基金 {code} HTTP {resp.status_code}")
                return None

            data = resp.json()
            items = data.get("data", []) or data.get("list", []) or []
            if not items:
                logger.warning(f"好买基金 {code} 返回空数据")
                return None

            all_dates, all_prices = [], []
            for item in items:
                # 好买字段：jzrq=净值日期，jjjz=基金净值
                date_str = item.get("jzrq", "") or item.get("date", "")
                nav_str = item.get("jjjz", "") or item.get("nav", "")
                if not date_str or not nav_str:
                    continue
                if not re.match(r"\d{4}-\d{2}-\d{2}", str(date_str)):
                    continue
                try:
                    all_dates.append(str(date_str))
                    all_prices.append(float(nav_str))
                except ValueError:
                    pass

            if not all_dates:
                return None

            unique = dict(zip(all_dates, all_prices))
            sorted_dates = sorted(unique.keys())
            sorted_prices = [unique[d] for d in sorted_dates]

            returns = [0]
            for i in range(1, len(sorted_prices)):
                try:
                    returns.append((sorted_prices[i] - sorted_prices[i - 1]) / sorted_prices[i - 1])
                except (ZeroDivisionError, TypeError):
                    returns.append(0)

            logger.info(f"好买基金共获取 {code} {len(sorted_prices)} 个数据点"
                        f"（{sorted_dates[0]} ~ {sorted_dates[-1]}）")
            return {"prices": sorted_prices, "dates": sorted_dates,
                    "returns": returns, "source": "好买基金"}
        except Exception as e:
            logger.error(f"从好买基金获取历史数据失败: {e}")
        return None

    def _get_fund_historical_data_tiantian_mobile(self, code):
        """获取基金历史净值数据（天天基金 App 移动端 API）

        与 PC 端 F10DataApi 不同的另一套接口，JSON 格式，每页最多 40 条，
        支持 page 参数，数据来源可信，适合作为东方财富 PC 接口的交叉验证。
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                              "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
                "Referer": "https://m.eastmoney.com/",
                "Accept": "application/json",
            }
            all_dates, all_prices = [], []
            PER_PAGE = 40
            MAX_PAGES = 20  # 20×40=800条，约3年

            for page in range(1, MAX_PAGES + 1):
                url = (f"https://api.m.eastmoney.com/mmfund/fundnav"
                       f"?code={code}&page={page}&pageSize={PER_PAGE}"
                       f"&callback=&deviceFlag=0")
                resp = requests.get(url, headers=headers, timeout=8, proxies=self.proxies)
                if resp.status_code != 200:
                    break

                # 接口返回 JSONP 或纯 JSON，先尝试直接解析
                text = resp.text.strip()
                # 去除可能的 JSONP 包装
                text = re.sub(r"^[a-zA-Z_$][a-zA-Z0-9_$]*\(", "", text).rstrip(");")
                try:
                    data = json.loads(text)
                except Exception:
                    break

                # 字段适配：不同版本可能是 Data / data / list
                items = (data.get("Data") or data.get("data") or
                         data.get("list") or [])
                if isinstance(items, dict):
                    items = items.get("LSJZList") or items.get("items") or []
                if not items:
                    logger.info(f"天天基金移动端 {code} 第{page}页无数据，停止")
                    break

                for item in items:
                    date_str = (item.get("FSRQ") or item.get("date")
                                or item.get("jzrq") or "")
                    nav_str = (item.get("DWJZ") or item.get("nav")
                               or item.get("jjjz") or "")
                    if not date_str or not nav_str:
                        continue
                    if not re.match(r"\d{4}-\d{2}-\d{2}", str(date_str)):
                        continue
                    try:
                        all_dates.append(str(date_str))
                        all_prices.append(float(nav_str))
                    except ValueError:
                        pass

                logger.info(f"天天基金移动端 {code} 第{page}页: {len(items)} 条，已累计 {len(all_dates)} 条")
                if len(all_dates) >= MAX_PAGES * PER_PAGE:
                    break

            if not all_dates:
                return None

            unique = dict(zip(all_dates, all_prices))
            sorted_dates = sorted(unique.keys())
            sorted_prices = [unique[d] for d in sorted_dates]

            returns = [0]
            for i in range(1, len(sorted_prices)):
                try:
                    returns.append((sorted_prices[i] - sorted_prices[i - 1]) / sorted_prices[i - 1])
                except (ZeroDivisionError, TypeError):
                    returns.append(0)

            logger.info(f"天天基金移动端共获取 {code} {len(sorted_prices)} 个数据点"
                        f"（{sorted_dates[0]} ~ {sorted_dates[-1]}）")
            return {"prices": sorted_prices, "dates": sorted_dates,
                    "returns": returns, "source": "天天基金移动端"}
        except Exception as e:
            logger.error(f"从天天基金移动端获取历史数据失败: {e}")
        return None

    def get_fund_holdings(self, code):
        """获取基金持仓股票数据（多数据源）"""
        data_list = []

        # 尝试从不同数据源获取数据
        for source in self.data_sources['holdings']:
            if not self._is_source_available(source):
                logger.warning(f"数据源 {source} 不可用，跳过")
                continue

            if source == 'eastmoney':
                result = self._get_fund_holdings_eastmoney(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从东方财富获取基金 {code} 持仓数据成功")
            elif source == '天天基金':
                result = self._get_fund_holdings_tiantian(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从天天基金获取基金 {code} 持仓数据成功")
            elif source == '同花顺':
                result = self._get_fund_holdings_ths(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从同花顺获取基金 {code} 持仓数据成功")

        # 验证数据一致性并选择最佳数据
        best_data = self.validate_data_consistency('holdings', data_list)
        if best_data:
            logger.info(f"选择最佳数据源: {best_data.get('source', '未知')}")
            return best_data

        logger.error(f"所有数据源获取基金 {code} 持仓数据失败")
        return None

    def _get_fund_holdings_eastmoney(self, code):
        """获取基金持仓股票数据（东方财富API）"""
        try:
            fund_data_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
            response = requests.get(fund_data_url, headers=self.headers, timeout=5, proxies=self.proxies)

            if response.status_code == 200:
                data_str = response.text

                # 尝试提取 Data_holdStock 变量（优先使用，包含真实持仓数据）
                data_hold_stock_match = re.search(r'var Data_holdStock = \[(.*?)\];', data_str, re.DOTALL)
                if data_hold_stock_match:
                    data_hold_stock_str = data_hold_stock_match.group(1)
                    try:
                        data_hold_stock = json.loads('[' + data_hold_stock_str + ']')

                        stocks = []
                        for stock in data_hold_stock:
                            try:
                                stock_code = stock.get('code', '')
                                stock_name = stock.get('name', '')
                                weight = stock.get('percent', 0) * 100  # 转换为百分比

                                if stock_code and stock_name and weight > 0:
                                    # 清理股票代码
                                    clean_code = stock_code.split('.')[0]
                                    if clean_code.isdigit() and len(clean_code) == 6:
                                        stock_info = {
                                            'code': clean_code,
                                            'name': stock_name,
                                            'weight': weight
                                        }
                                        stocks.append(stock_info)
                            except Exception:
                                pass

                        # 尝试提取资产配置数据
                        stock_ratio = 0
                        asset_match = re.search(r'var Data_assetAllocation = \[(.*?)\];', data_str, re.DOTALL)
                        if asset_match:
                            try:
                                asset_data = asset_match.group(1)
                                # 尝试解析资产配置数据
                                if '{' in asset_data:
                                    # 尝试解析为JSON
                                    try:
                                        asset_json = json.loads('[' + asset_data + ']')
                                        for item in asset_json:
                                            if item.get('assetType') == '股票' or item.get('name') == '股票':
                                                stock_ratio = float(item.get('ratio', 0)) * 100
                                                break
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                        # 如果没有提取到资产配置数据，尝试从其他地方获取
                        if stock_ratio == 0 and stocks:
                            # 计算股票总权重作为股票占比
                            total_weight = sum(stock['weight'] for stock in stocks)
                            if total_weight > 0:
                                stock_ratio = min(total_weight, 100.0)

                        return {
                            'stocks': stocks,
                            'stock_ratio': stock_ratio,
                            'source': '东方财富'
                        }
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"从东方财富获取基金持仓数据失败: {e}")
        return None

    def _get_fund_holdings_tiantian(self, code):
        """获取基金持仓股票数据（天天基金网API）"""
        try:
            fund_data_url = f"https://fund.eastmoney.com/f10/ccmx_{code}.html"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": f"https://fund.eastmoney.com/{code}.html",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive"
            }

            response = requests.get(fund_data_url, headers=headers, timeout=5, proxies=self.proxies)

            if response.status_code == 200:
                content = response.text
                # 解析天天基金网的持仓数据
                # 这里只是一个示例，实际需要根据天天基金网的页面结构进行调整
                logger.info(f"天天基金持仓数据返回: {content[:100]}...")
                # 由于页面结构可能变化，这里暂时返回None
                # 实际使用时需要根据具体页面结构进行解析
        except Exception as e:
            logger.error(f"从天天基金获取基金持仓数据失败: {e}")
        return None

    def _get_fund_holdings_ths(self, code):
        """获取基金持仓股票数据（同花顺API）"""
        try:
            fund_url = f"http://fund.10jqka.com.cn/{code}/cc/"
            response = requests.get(fund_url, headers=self.headers, timeout=5, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 解析HTML获取持仓数据
                stocks = []

                # 简单的解析，实际需要根据同花顺页面结构调整
                # 这里使用正则表达式提取数据
                # 实际实现需要根据同花顺页面的具体结构进行调整

                return {
                    'stocks': stocks,
                    'stock_ratio': 0,
                    'source': '同花顺'
                }
        except Exception as e:
            logger.error(f"从同花顺获取基金持仓数据失败: {e}")
        return None

    def get_fund_estimated_return(self, code):
        """获取基金当日预估收益率（多数据源）"""
        data_list = []

        # 尝试从不同数据源获取数据
        for source in self.data_sources['estimated_return']:
            if not self._is_source_available(source):
                logger.warning(f"数据源 {source} 不可用，跳过")
                continue

            if source == 'sina':
                result = self._get_fund_estimated_return_sina(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从新浪财经获取基金 {code} 预估收益率成功")
            elif source == 'eastmoney':
                result = self._get_fund_estimated_return_eastmoney(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从东方财富获取基金 {code} 预估收益率成功")

        # 验证数据一致性并选择最佳数据
        best_data = self.validate_data_consistency('estimated_return', data_list)
        if best_data:
            logger.info(f"选择最佳数据源: {best_data.get('source', '未知')}")
            return best_data

        logger.error(f"所有数据源获取基金 {code} 预估收益率失败")
        return None

    def _get_fund_estimated_return_sina(self, code):
        """获取基金当日预估收益率（新浪财经API）"""
        try:
            fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            response = requests.get(fund_url, headers=self.headers, timeout=3, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                data_str = response.text.strip().replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)
                return {
                    'gsz': float(data.get('gsz', 0)),
                    'gszzl': float(data.get('gszzl', 0)) / 100,
                    'gztime': data.get('gztime'),
                    'source': '新浪财经'
                }
        except Exception as e:
            logger.error(f"从新浪财经获取基金预估收益率失败: {e}")
        return None

    def _get_fund_estimated_return_tencent(self, code):
        """获取基金当日预估收益率（腾讯财经API）"""
        try:
            fund_url = f"https://fund.qq.com/cgi-bin/fundquery/FundInfoGet?vname=jjsqjz&fundcode={code}"
            response = requests.get(fund_url, headers=self.headers, timeout=3, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 解析腾讯财经返回的数据
                data_str = response.text
                # 腾讯财经的返回格式可能需要特殊处理
                logger.info(f"腾讯财经预估收益率返回: {data_str[:100]}...")
                # 由于腾讯财经API格式可能变化，这里暂时返回None
                # 实际使用时需要根据具体API格式进行解析
        except Exception as e:
            logger.error(f"从腾讯财经获取基金预估收益率失败: {e}")
        return None

    def _get_fund_estimated_return_eastmoney(self, code):
        """获取基金当日预估收益率（东方财富API）"""
        try:
            fund_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
            response = requests.get(fund_url, headers=self.headers, timeout=3, proxies=self.proxies)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                data_str = response.text
                # 提取基金预估收益率相关数据
                gsz_match = re.search(r'var gsz = (.*?);', data_str)
                gszzl_match = re.search(r'var gszzl = (.*?);', data_str)
                gztime_match = re.search(r'var gztime = "(.*?)";', data_str)

                if gsz_match and gszzl_match:
                    gsz = float(gsz_match.group(1))
                    gszzl = float(gszzl_match.group(1)) / 100  # 转换为小数
                    gztime = gztime_match.group(1) if gztime_match else datetime.now().strftime('%Y-%m-%d %H:%M')

                    return {
                        'gsz': gsz,
                        'gszzl': gszzl,
                        'gztime': gztime,
                        'source': '东方财富'
                    }
        except Exception as e:
            logger.error(f"从东方财富获取基金预估收益率失败: {e}")
        return None

    def _update_source_health(self, source, success):
        """更新数据源健康状态"""
        self.source_health[source]['last_checked'] = datetime.now()
        if success:
            if self.source_health[source]['status'] == 'unhealthy':
                logger.info(f"数据源 {source} 已恢复健康状态")
            self.source_health[source]['status'] = 'healthy'
            self.source_health[source]['fail_count'] = 0
        else:
            self.source_health[source]['fail_count'] += 1
            if self.source_health[source]['fail_count'] >= self.health_threshold:
                if self.source_health[source]['status'] != 'unhealthy':
                    logger.warning(
                        f"数据源 {source} 连续失败 {self.source_health[source]['fail_count']} 次，标记为不健康")
                self.source_health[source]['status'] = 'unhealthy'

    def _is_source_available(self, source):
        """检查数据源是否可用"""
        health = self.source_health[source]
        if health['status'] == 'healthy':
            return True
        else:
            # 检查是否超过重试间隔
            time_since_last_check = (datetime.now() - health['last_checked']).total_seconds()
            if time_since_last_check >= self.retry_interval:
                # 尝试恢复数据源
                logger.info(f"尝试恢复数据源 {source}")
                return True
            else:
                return False

    def get_source_health_status(self):
        """获取所有数据源的健康状态"""
        status = {}
        for source, health in self.source_health.items():
            status[source] = {
                'status': health['status'],
                'fail_count': health['fail_count'],
                'last_checked': health['last_checked'].strftime('%Y-%m-%d %H:%M:%S')
            }
        return status

    def validate_data_consistency(self, data_type, data_list):
        """验证数据一致性"""
        if not data_list:
            return None

        # 对于不同类型的数据，使用不同的一致性验证方法
        if data_type == 'latest_nav':
            # 验证最新净值数据一致性
            valid_data = [d for d in data_list if d and 'dwjz' in d and d['dwjz'] > 0]
            if valid_data:
                # 按数据来源的优先级排序
                source_priority = self.data_sources['latest_nav']
                valid_data.sort(key=lambda x: source_priority.index(x.get('source', 'unknown')) if x.get('source',
                                                                                                         'unknown') in source_priority else len(
                    source_priority))
                return valid_data[0]
        elif data_type == 'estimated_return':
            # 验证预估收益率数据一致性
            valid_data = [d for d in data_list if d and 'gszzl' in d]
            if valid_data:
                # 计算平均值并选择最接近平均值的数据
                avg_return = sum(d['gszzl'] for d in valid_data) / len(valid_data)
                valid_data.sort(key=lambda x: abs(x['gszzl'] - avg_return))
                return valid_data[0]
        elif data_type == 'holdings':
            # 验证持仓数据一致性
            valid_data = [d for d in data_list if d and 'stocks' in d and len(d['stocks']) > 0]
            if valid_data:
                # 选择股票数量最多的数据源
                valid_data.sort(key=lambda x: len(x['stocks']), reverse=True)
                return valid_data[0]
        elif data_type == 'historical_data':
            # 验证历史数据一致性
            valid_data = [d for d in data_list if d and 'prices' in d and len(d['prices']) > 0]
            if valid_data:
                # 选择数据点最多的数据源
                valid_data.sort(key=lambda x: len(x['prices']), reverse=True)
                return valid_data[0]

        return None

    def get_stock_real_time_data(self, stock_code):
        """获取股票实时数据（新浪财经API）"""
        try:
            # 对于沪市股票，需要添加sh前缀；深市股票添加sz前缀
            if stock_code.startswith('6'):
                full_code = f"sh{stock_code}"
            else:
                full_code = f"sz{stock_code}"

            stock_url = f"http://hq.sinajs.cn/list={full_code}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://finance.sina.com.cn/"
            }
            response = requests.get(stock_url, headers=headers, timeout=3, proxies=self.proxies)

            if response.status_code == 200:
                stock_data = response.text
                # 解析股票数据
                name_match = re.search(r'"(.*?),', stock_data)
                if name_match:
                    stock_name = name_match.group(1)
                else:
                    stock_name = f"股票{stock_code}"

                # 解析价格数据
                data_part = stock_data.split('=', 1)[1].strip('"')
                stock_info = data_part.split(',')
                if len(stock_info) > 3:
                    # 计算涨跌幅
                    current_price = float(stock_info[3])
                    previous_close = float(stock_info[2])
                    if previous_close > 0:
                        change = (current_price - previous_close) / previous_close
                        change_amount = current_price - previous_close
                        return {
                            'name': stock_name,
                            'current_price': current_price,
                            'change_amount': change_amount,
                            'change_ratio': change
                        }
        except Exception as e:
            logger.error(f"获取股票实时数据失败: {e}")
        return None

    def get_market_data(self):
        """获取市场数据（新浪财经API）"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://finance.sina.com.cn/"
            }

            # 主要大盘指数
            index_codes = {
                'sh000001': '上证指数',
                'sz399001': '深证成指',
                'sz399006': '创业板指',
                'sh000300': '沪深300'
            }

            # 主要行业板块
            sector_codes = {
                'sh000037': '医药制造',
                'sh000039': '食品饮料',
                'sh000043': '信息技术',
                'sh000063': '电子元件',
                'sh000048': '银行',
                'sh000046': '房地产',
                'sh000042': '电力',
                'sh000044': '通信设备',
                'sh000041': '航天航空',
                'sh000038': '纺织服装',
                'sh000040': '有色金属',
                'sh000045': '建筑材料',
                'sh000047': '交通运输',
                'sh000049': '煤炭',
                'sh000050': '石油',
                'sh000051': '钢铁',
                'sh000052': '化工',
                'sh000053': '机械',
                'sh000054': '汽车'
            }

            # 构建API URL
            all_codes = list(index_codes.keys()) + list(sector_codes.keys())
            code_str = ",".join(all_codes)
            market_url = f"http://hq.sinajs.cn/list={code_str}"
            response = requests.get(market_url, headers=headers, timeout=5, proxies=self.proxies)

            if response.status_code == 200:
                market_data = response.text

                # 解析数据
                lines = market_data.strip().split('\n')
                result = {
                    'indices': {},
                    'sectors': {}
                }

                for line in lines:
                    if '=' in line:
                        try:
                            code_part, data_part = line.split('=', 1)
                            code = code_part.split('_')[-1]
                            data = data_part.strip('"').split(',')

                            if len(data) > 3:
                                current_price = float(data[3])
                                previous_close = float(data[2])
                                if previous_close > 0:
                                    change = (current_price - previous_close) / previous_close
                                    change_amount = current_price - previous_close

                                    if code in index_codes:
                                        result['indices'][index_codes[code]] = {
                                            'code': code,
                                            'current_price': current_price,
                                            'change_amount': change_amount,
                                            'change_ratio': change
                                        }
                                    elif code in sector_codes:
                                        result['sectors'][sector_codes[code]] = {
                                            'code': code,
                                            'current_price': current_price,
                                            'change_amount': change_amount,
                                            'change_ratio': change
                                        }
                        except Exception as e:
                            logger.error(f"解析市场数据失败: {e}")

                return result
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
        return {'indices': {}, 'sectors': {}}


# 创建数据源管理器实例
data_source_manager = DataSourceManager()