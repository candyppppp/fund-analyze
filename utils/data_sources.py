import requests
import json
import re
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DataSourceManager:
    """数据源管理类，用于管理不同的数据源"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # 数据源配置 - 只保留稳定可用的数据源
        self.data_sources = {
            'latest_nav': ['sina', 'eastmoney'],  # 最新净值数据源优先级
            'historical_data': ['sina', '天天基金', 'eastmoney'],  # 历史数据数据源优先级，优先使用新浪财经和天天基金
            'holdings': ['eastmoney', '天天基金'],  # 持仓数据数据源优先级
            'estimated_return': ['sina', 'eastmoney']  # 预估收益率数据源优先级
        }
        # 数据源健康状态 - 只保留稳定可用的数据源
        self.source_health = {
            'sina': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
            'eastmoney': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0},
            '天天基金': {'status': 'healthy', 'last_checked': datetime.now(), 'fail_count': 0}
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
            response = requests.get(fund_url, headers=self.headers, timeout=3)
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
            response = requests.get(fund_url, headers=self.headers, timeout=3)
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
    
    def get_fund_historical_data(self, code):
        """获取基金历史净值数据（多数据源）"""
        data_list = []
        
        # 尝试从不同数据源获取数据
        for source in self.data_sources['historical_data']:
            if not self._is_source_available(source):
                logger.warning(f"数据源 {source} 不可用，跳过")
                continue
            
            if source == 'eastmoney':
                result = self._get_fund_historical_data_eastmoney(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从东方财富获取基金 {code} 历史数据成功")
            elif source == '天天基金':
                result = self._get_fund_historical_data_tiantian(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从天天基金获取基金 {code} 历史数据成功")
            elif source == 'sina':
                result = self._get_fund_historical_data_sina(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从新浪财经获取基金 {code} 历史数据成功")
            elif source == 'tencent':
                result = self._get_fund_historical_data_tencent(code)
                self._update_source_health(source, result is not None)
                if result:
                    data_list.append(result)
                    logger.info(f"从腾讯财经获取基金 {code} 历史数据成功")
        
        # 验证数据一致性并选择最佳数据
        best_data = self.validate_data_consistency('historical_data', data_list)
        if best_data:
            logger.info(f"选择最佳数据源: {best_data.get('source', '未知')}")
            return best_data
        
        logger.error(f"所有数据源获取基金 {code} 历史数据失败")
        return None
    
    def _get_fund_historical_data_eastmoney(self, code):
        """获取基金历史净值数据（东方财富API）"""
        try:
            all_prices = []
            all_dates = []
            
            # 分页获取数据，每页20条，获取20页，共400条数据
            for page in range(1, 21):
                fund_data_url = f"http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code={code}&page={page}&per=20"
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": f"http://fund.eastmoney.com/{code}.html",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Connection": "keep-alive"
                }
                
                response = requests.get(fund_data_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    content_start = response.text.find('content:"')
                    if content_start != -1:
                        content_start += len('content:"')
                        content_end = response.text.find('"', content_start)
                        if content_end != -1:
                            content = response.text[content_start:content_end]
                            table_start = content.find('<table')
                            table_end = content.find('</table>', table_start)
                            if table_start != -1 and table_end != -1:
                                table_html = content[table_start:table_end + len('</table>')]
                                row_start = table_html.find('<tr')
                                rows = []
                                while row_start != -1:
                                    row_end = table_html.find('</tr>', row_start)
                                    if row_end != -1:
                                        rows.append(table_html[row_start:row_end + len('</tr>')])
                                        row_start = table_html.find('<tr', row_end)
                                    else:
                                        break
                                
                                page_prices = []
                                page_dates = []
                                
                                for i, row in enumerate(rows):
                                    if i == 0:
                                        continue
                                    col_start = row.find('<td')
                                    cols = []
                                    while col_start != -1:
                                        col_end = row.find('</td>', col_start)
                                        if col_end != -1:
                                            col_content = row[col_start:col_end + len('</td>')]
                                            col_text = col_content.replace('<td', '').replace('</td>', '').replace('class="tor bold"', '').replace('class="tor bold red"', '').replace('class="red unbold"', '').strip()
                                            text_start = col_text.find('>')
                                            if text_start != -1:
                                                col_text = col_text[text_start + 1:].strip()
                                            cols.append(col_text)
                                            col_start = row.find('<td', col_end)
                                        else:
                                            break
                                    
                                    if len(cols) >= 4:
                                        date_str = cols[0]
                                        nav_str = cols[1]
                                        try:
                                            nav = float(nav_str)
                                            page_prices.append(nav)
                                            page_dates.append(date_str)
                                        except ValueError:
                                            pass
                                
                                # 如果没有数据，说明已经到最后一页
                                if len(page_prices) == 0:
                                    break
                                
                                all_prices.extend(page_prices)
                                all_dates.extend(page_dates)
                
                # 避免请求过于频繁，添加延迟
                time.sleep(0.1)
            
            # 反转数据，使日期从旧到新
            all_prices.reverse()
            all_dates.reverse()
            
            # 计算收益率
            returns = []
            if len(all_prices) > 1:
                for i in range(1, len(all_prices)):
                    try:
                        daily_return = (all_prices[i] - all_prices[i-1]) / all_prices[i-1]
                        returns.append(daily_return)
                    except (ZeroDivisionError, TypeError):
                        returns.append(0)
                returns.insert(0, 0)
            
            logger.info(f"东方财富API返回了 {len(all_prices)} 个数据点")
            
            return {
                'prices': all_prices,
                'dates': all_dates,
                'returns': returns,
                'source': '东方财富'
            }
        except Exception as e:
            logger.error(f"从东方财富获取基金历史数据失败: {e}")
        return None
    
    def _get_fund_historical_data_tiantian(self, code):
        """获取基金历史净值数据（天天基金网API）"""
        try:
            # 增加数据获取量到365条，覆盖一年的数据
            fund_data_url = f"http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code={code}&page=1&per=365"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": f"http://fund.eastmoney.com/{code}.html",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive"
            }
            
            response = requests.get(fund_data_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                content_start = response.text.find('content:"')
                if content_start != -1:
                    content_start += len('content:"')
                    content_end = response.text.find('"', content_start)
                    if content_end != -1:
                        content = response.text[content_start:content_end]
                        table_start = content.find('<table')
                        table_end = content.find('</table>', table_start)
                        if table_start != -1 and table_end != -1:
                            table_html = content[table_start:table_end + len('</table>')]
                            row_start = table_html.find('<tr')
                            rows = []
                            while row_start != -1:
                                row_end = table_html.find('</tr>', row_start)
                                if row_end != -1:
                                    rows.append(table_html[row_start:row_end + len('</tr>')])
                                    row_start = table_html.find('<tr', row_end)
                                else:
                                    break
                            
                            prices = []
                            dates = []
                            returns = []
                            
                            for i, row in enumerate(rows):
                                if i == 0:
                                    continue
                                col_start = row.find('<td')
                                cols = []
                                while col_start != -1:
                                    col_end = row.find('</td>', col_start)
                                    if col_end != -1:
                                        col_content = row[col_start:col_end + len('</td>')]
                                        col_text = col_content.replace('<td', '').replace('</td>', '').replace('class="tor bold"', '').replace('class="tor bold red"', '').replace('class="red unbold"', '').strip()
                                        text_start = col_text.find('>')
                                        if text_start != -1:
                                            col_text = col_text[text_start + 1:].strip()
                                        cols.append(col_text)
                                        col_start = row.find('<td', col_end)
                                    else:
                                        break
                                
                                if len(cols) >= 4:
                                    date_str = cols[0]
                                    nav_str = cols[1]
                                    try:
                                        nav = float(nav_str)
                                        prices.append(nav)
                                        dates.append(date_str)
                                    except ValueError:
                                        pass
                            
                            # 反转数据，使日期从旧到新
                            prices.reverse()
                            dates.reverse()
                            
                            # 计算收益率
                            if len(prices) > 1:
                                for i in range(1, len(prices)):
                                    try:
                                        daily_return = (prices[i] - prices[i-1]) / prices[i-1]
                                        returns.append(daily_return)
                                    except (ZeroDivisionError, TypeError):
                                        returns.append(0)
                                returns.insert(0, 0)
                            
                            return {
                                'prices': prices,
                                'dates': dates,
                                'returns': returns,
                                'source': '天天基金'
                            }
        except Exception as e:
            logger.error(f"从天天基金网获取基金历史数据失败: {e}")
        return None
    
    def _get_fund_historical_data_sina(self, code):
        """获取基金历史净值数据（新浪财经API）"""
        try:
            # 首先获取最新净值数据
            fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            response = requests.get(fund_url, headers=self.headers, timeout=5)
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
                response_history = requests.get(history_url, headers=self.headers, timeout=5)
                
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
                            daily_return = (prices[i] - prices[i-1]) / prices[i-1]
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
    
    def _get_fund_historical_data_tencent(self, code):
        """获取基金历史净值数据（腾讯财经API）"""
        try:
            # 使用新浪财经的API作为备用数据源
            fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            response = requests.get(fund_url, headers=self.headers, timeout=5)
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
                
                # 由于新浪财经API只返回最新数据，我们需要使用其他方式获取历史数据
                # 这里我们使用东方财富的API作为补充
                eastmoney_data = self._get_fund_historical_data_eastmoney(code)
                if eastmoney_data:
                    prices.extend(eastmoney_data['prices'])
                    dates.extend(eastmoney_data['dates'])
                    returns = eastmoney_data['returns']
                
                # 去重处理
                unique_data = {}
                for date, price in zip(dates, prices):
                    unique_data[date] = price
                
                # 按日期排序
                sorted_dates = sorted(unique_data.keys())
                sorted_prices = [unique_data[date] for date in sorted_dates]
                
                # 计算收益率
                if len(sorted_prices) > 1 and not returns:
                    returns = []
                    for i in range(1, len(sorted_prices)):
                        try:
                            daily_return = (sorted_prices[i] - sorted_prices[i-1]) / sorted_prices[i-1]
                            returns.append(daily_return)
                        except (ZeroDivisionError, TypeError):
                            returns.append(0)
                    returns.insert(0, 0)
                
                return {
                    'prices': sorted_prices,
                    'dates': sorted_dates,
                    'returns': returns,
                    'source': '腾讯财经'
                }
        except Exception as e:
            logger.error(f"从腾讯财经获取基金历史数据失败: {e}")
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
            response = requests.get(fund_data_url, headers=self.headers, timeout=5)
            
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
            
            response = requests.get(fund_data_url, headers=headers, timeout=5)
            
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
            response = requests.get(fund_url, headers=self.headers, timeout=3)
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
            response = requests.get(fund_url, headers=self.headers, timeout=3)
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
            response = requests.get(fund_url, headers=self.headers, timeout=3)
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
                    logger.warning(f"数据源 {source} 连续失败 {self.source_health[source]['fail_count']} 次，标记为不健康")
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
                valid_data.sort(key=lambda x: source_priority.index(x.get('source', 'unknown')) if x.get('source', 'unknown') in source_priority else len(source_priority))
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
            response = requests.get(stock_url, headers=headers, timeout=3)
            
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
            response = requests.get(market_url, headers=headers, timeout=5)
            
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
