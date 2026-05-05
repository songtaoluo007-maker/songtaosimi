"""
OCR截图识别服务
使用PaddleOCR识别支付宝/同花顺APP持仓截图及交易记录截图
"""
import re
import traceback
from datetime import datetime
from loguru import logger
from typing import List, Dict
from backend.services.fund_nav_collector import fetch_fund_info, fetch_latest_nav
from backend.database import SessionLocal
from backend.models.fund import Fund


class OcrService:
    def __init__(self):
        self.ocr = None
        self._ocr_type = "none"

    def _get_ocr(self):
        """懒加载OCR引擎（优先PaddleOCR，备选RapidOCR）"""
        if self.ocr is None:
            # 尝试PaddleOCR
            try:
                from paddleocr import PaddleOCR
                self.ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    show_log=False,
                    use_gpu=False,
                )
                self._ocr_type = "paddle"
                return self.ocr
            except ImportError:
                logger.warning("PaddleOCR未安装，尝试RapidOCR...")

            # 尝试RapidOCR
            try:
                from rapidocr_onnxruntime import RapidOCR
                self.ocr = RapidOCR()
                self._ocr_type = "rapid"
                return self.ocr
            except ImportError:
                logger.error("PaddleOCR和RapidOCR均未安装，请运行: pip install rapidocr-onnxruntime")
                raise RuntimeError("OCR引擎未安装，请安装 rapidocr-onnxruntime 或 paddleocr")
        return self.ocr

    def recognize(self, image_path: str, source: str) -> List[Dict]:
        """
        识别截图中的持仓信息

        Args:
            image_path: 截图文件路径
            source: 来源 "alipay" 或 "tiantian"(同花顺)

        Returns:
            识别结果列表 [{"fund_code": "", "fund_name": "", "shares": 0, "amount": 0}]
        """
        try:
            ocr = self._get_ocr()

            if self._ocr_type == "rapid":
                # RapidOCR: 直接调用，返回 (result, elapsed)
                result, _ = ocr(image_path)
                if not result:
                    return [{"error": "OCR未识别到文字", "image": image_path}]
                texts = []
                for item in result:
                    box = item[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                    text = item[1]
                    confidence = item[2]
                    texts.append({
                        "text": text,
                        "box": box,
                        "confidence": confidence,
                    })
            else:
                # PaddleOCR返回格式
                result = ocr.ocr(image_path, cls=True)
                if not result or not result[0]:
                    return [{"error": "OCR未识别到文字", "image": image_path}]
                texts = []
                for line in result[0]:
                    box = line[0]
                    text = line[1][0]
                    confidence = line[1][1]
                    texts.append({
                        "text": text,
                        "box": box,
                        "confidence": confidence,
                    })

            # 根据来源选择解析模板
            if source == "tiantian_trades":
                results = self._parse_tiantian_trades(texts)
            elif source == "alipay":
                results = self._parse_alipay(texts)
            elif source == "tiantian":
                results = self._parse_tiantian(texts)
            else:
                results = self._parse_generic(texts)

            # 交易记录来源：联网补全基金代码
            if source == "tiantian_trades":
                self._fill_fund_codes(results)

            # 统一联网补全基金信息（名称、净值、份额）— 所有source都走这一步
            results = self._enrich_fund_info(results)

            return results

        except Exception as e:
            logger.error(f"OCR识别失败: {e}\n{traceback.format_exc()}")
            return [{"error": str(e)}]

    def _enrich_fund_info(self, results: List[Dict]) -> List[Dict]:
        """
        通用基金信息补全：用基金代码联网查询官方名称
        适用于所有OCR解析结果（持仓和交易记录）

        策略：
        1. 收集所有有效的基金代码
        2. 批量联网查询（用dict缓存避免重复查询）
        3. 用官方名称替换OCR拼接的名称（仅当查询成功时）
        4. OCR名称作为降级保留
        """
        cache = {}  # fund_code -> fund_info

        for item in results:
            # 跳过错误项
            if "error" in item:
                continue

            code = item.get("fund_code", "").strip()
            if not code or not re.match(r'^\d{6}$', code):
                continue

            # 查缓存，未命中则联网查询
            if code not in cache:
                try:
                    info = fetch_fund_info(code)
                    cache[code] = info  # info 可能为 None 或无 fund_name
                except Exception as e:
                    logger.warning(f"联网查询基金{code}信息失败: {e}")
                    cache[code] = None

            info = cache.get(code)
            if info and info.get("fund_name"):
                # 用官方名称替换OCR名称（核心逻辑）
                item["fund_name"] = info["fund_name"]
                logger.debug(f"基金{code}名称已补全: {info['fund_name']}")

            # 推算份额：有金额无份额时，用最新净值推算
            amount = float(item.get("amount", 0) or 0)
            shares = float(item.get("shares", 0) or 0)
            if amount > 0 and shares <= 0:
                try:
                    nav = fetch_latest_nav(code)
                    if nav > 0:
                        item["shares"] = round(amount / nav, 2)
                        item["nav"] = nav
                except Exception:
                    pass

            # 支付宝来源：补全成本推算
            if item.get("source") == "alipay":
                cost = float(item.get("cost_amount", 0) or 0)
                if cost <= 0 and amount > 0:
                    item["cost_amount"] = amount

        return results

    def _clean_amount_text(self, text: str) -> str:
        """预处理金额文本"""
        text = text.strip()
        # 去除货币符号
        text = re.sub(r'[¥￥$€]', '', text)
        # 去除"万""元"等单位
        text = re.sub(r'[万元]$', '', text)
        # 替换中文句号为英文
        text = text.replace('．', '.').replace('。', '.')
        # 去除数字间的空格
        text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
        # 去除千位逗号
        text = text.replace(',', '')
        return text

    def _extract_fund_code(self, text: str) -> str:
        """从文本中提取6位基金代码"""
        match = re.search(r'\b(\d{6})\b', text)
        return match.group(1) if match else ""

    def _extract_amount(self, text: str) -> float:
        """从文本中提取金额"""
        # 匹配各种金额格式
        patterns = [
            r'[¥￥]?\s*([\d,]+\.?\d*)',  # ¥1,234.56
            r'([\d,]+\.?\d*)\s*[元万]?',  # 1234.56元
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                val = match.group(1).replace(",", "")
                try:
                    return float(val)
                except ValueError:
                    continue
        return 0.0

    def _extract_daily_pnl_date(self, texts: List[Dict]) -> str:
        """从截图表头里提取 04-24 这类收益日期，补全年份后返回 ISO 日期。"""
        all_text = " ".join(t.get("text", "") for t in texts)
        match = re.search(r'(?<!\d)(\d{1,2})[-/.](\d{1,2})(?!\d)', all_text)
        if not match:
            return ""
        try:
            return datetime(datetime.now().year, int(match.group(1)), int(match.group(2))).date().isoformat()
        except ValueError:
            return ""

    def _parse_number_token(self, text: str):
        cleaned = self._clean_amount_text(text)
        if re.match(r'^[+-]?[\d.]+$', cleaned):
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _parse_tiantian_by_code_windows(self, items: List[Dict], code_items: List[Dict], median_height: float, daily_pnl_date: str) -> List[Dict]:
        """以基金代码为锚点解析持仓行，兼容长名称折行和不同手机字号。"""
        width = max((it["x_center"] for it in items), default=0) + median_height
        code_items = sorted(code_items, key=lambda x: x["y_center"])
        code_pattern = re.compile(r'^\d{6}$')
        date_pattern = re.compile(r'^\d{1,2}[-/.]\d{1,2}$')
        header_keywords = ("我的持仓", "基金名称", "总金额", "日收益", "持有收益", "收益率", "总金额排序")
        results = []

        for idx, code_item in enumerate(code_items):
            code = code_item["text"]
            code_y = code_item["y_center"]
            prev_y = code_items[idx - 1]["y_center"] if idx > 0 else code_y - median_height * 6
            next_y = code_items[idx + 1]["y_center"] if idx + 1 < len(code_items) else code_y + median_height * 6
            top_bound = (prev_y + code_y) / 2
            bottom_bound = (code_y + next_y) / 2
            window = [it for it in items if top_bound <= it["y_center"] < bottom_bound and not date_pattern.match(it["text"].strip())]

            name_parts = []
            numeric_tokens = []
            pct_tokens = []
            for it in sorted(window, key=lambda x: (x["y_center"], x["x_center"])):
                text = it["text"].strip()
                if code_pattern.match(text) or any(kw in text for kw in header_keywords):
                    continue
                if "%" in text:
                    pct_match = re.search(r'[+-]?[\d,.]+', text)
                    if pct_match:
                        try:
                            pct_tokens.append({**it, "value": float(pct_match.group().replace(",", ""))})
                        except ValueError:
                            pass
                    continue
                value = self._parse_number_token(text)
                if value is not None:
                    numeric_tokens.append({**it, "value": value})
                    continue
                if it["x_center"] < width * 0.52 and len(text) >= 2:
                    name_parts.append(text)

            mid_nums = sorted([n for n in numeric_tokens if width * 0.43 <= n["x_center"] <= width * 0.78], key=lambda x: (x["y_center"], x["x_center"]))
            right_nums = sorted([n for n in numeric_tokens if n["x_center"] > width * 0.80], key=lambda x: (x["y_center"], x["x_center"]))

            amount = 0.0
            daily_pnl = 0.0
            if mid_nums:
                amount_candidates = [n for n in mid_nums if abs(n["value"]) >= 30 and n["y_center"] < code_y]
                amount_item = amount_candidates[0] if amount_candidates else mid_nums[0]
                amount = abs(amount_item["value"])
                daily_candidates = [n for n in mid_nums if n is not amount_item and (n["y_center"] >= amount_item["y_center"] or n["text"].startswith(("+", "-")))]
                if daily_candidates:
                    daily_pnl = daily_candidates[-1]["value"]

            holding_pnl = 0.0
            if right_nums:
                holding_candidates = [n for n in right_nums if n["y_center"] < code_y or n["text"].startswith(("+", "-"))]
                holding_pnl = (holding_candidates[0] if holding_candidates else right_nums[0])["value"]
            holding_pnl_pct = pct_tokens[0]["value"] if pct_tokens else 0.0

            cost_amount = 0.0
            if amount > 0:
                cost_amount = round(amount - holding_pnl, 2) if holding_pnl != 0 else (
                    round(amount * 100 / (100 + holding_pnl_pct), 2) if holding_pnl_pct != 0 else amount
                )

            if name_parts or amount or daily_pnl or holding_pnl or holding_pnl_pct:
                results.append({
                    "fund_code": code,
                    "fund_name": "".join(name_parts).strip() or f"基金{code}",
                    "shares": 0,
                    "amount": round(amount, 2),
                    "cost_amount": round(cost_amount, 2),
                    "holding_pnl": round(holding_pnl, 2),
                    "holding_pnl_pct": round(holding_pnl_pct, 2),
                    "daily_pnl": round(daily_pnl, 2),
                    "daily_pnl_date": daily_pnl_date,
                    "nav": 0,
                    "source": "tiantian",
                })

        return results

    def _parse_alipay(self, texts: List[Dict]) -> List[Dict]:
        """
        解析支付宝基金持仓截图

        支付宝截图特征：
        - 基金名称通常在一行的开头
        - 金额通常显示为"持有金额 xxx"
        - 可能有"昨日收益 xxx"
        """
        results = []
        all_text = " ".join(t["text"] for t in texts)

        # 尝试提取基金代码
        fund_codes = re.findall(r'\b(\d{6})\b', all_text)

        # 尝试提取基金名称（通常包含"混合"、"股票"、"债券"、"ETF"等关键词）
        fund_names = []
        for t in texts:
            text = t["text"]
            if any(kw in text for kw in ["混合", "股票", "债券", "ETF", "指数", "FOF", "LOF", "QDII"]):
                fund_names.append(text)

        # 尝试提取金额
        amounts = []
        for t in texts:
            text = t["text"]
            if "持有" in text or "金额" in text:
                amt = self._extract_amount(text)
                if amt > 0:
                    amounts.append(amt)

        # 尝试提取持有收益
        holding_pnls = []
        for t in texts:
            text = t["text"]
            if "持有收益" in text or "累计收益" in text:
                amt = self._extract_amount(text)
                if amt != 0:
                    holding_pnls.append(amt)
                # 也尝试匹配带正负号的
                sign_match = re.search(r'([+-]?[\d,]+\.?\d*)', text)
                if sign_match and amt == 0:
                    try:
                        holding_pnls.append(float(sign_match.group(1).replace(',', '')))
                    except ValueError:
                        pass

        # 尝试提取收益率
        holding_pnl_pcts = []
        for t in texts:
            text = t["text"]
            pct_match = re.search(r'([+-]?[\d.]+)%', text)
            if pct_match:
                try:
                    holding_pnl_pcts.append(float(pct_match.group(1)))
                except ValueError:
                    pass

        # 组合结果
        for i, code in enumerate(fund_codes):
            name = fund_names[i] if i < len(fund_names) else f"基金{code}"
            amount = amounts[i] if i < len(amounts) else 0
            holding_pnl = holding_pnls[i] if i < len(holding_pnls) else 0
            holding_pnl_pct = holding_pnl_pcts[i] if i < len(holding_pnl_pcts) else 0

            # 推算成本（参考同花顺逻辑）
            cost_amount = 0.0
            if amount > 0:
                if holding_pnl_pct != 0:
                    cost_amount = round(amount * 100 / (100 + holding_pnl_pct), 2)
                elif holding_pnl != 0:
                    cost_amount = round(amount - holding_pnl, 2)
                else:
                    cost_amount = amount

            results.append({
                "fund_code": code,
                "fund_name": name,
                "shares": 0,
                "amount": amount,
                "cost_amount": cost_amount,
                "holding_pnl": round(holding_pnl, 2),
                "holding_pnl_pct": round(holding_pnl_pct, 2),
                "source": "alipay",
            })

        # 如果没有找到代码，尝试用名称匹配
        if not fund_codes and fund_names:
            for name in fund_names:
                results.append({
                    "fund_code": "",
                    "fund_name": name,
                    "shares": 0,
                    "amount": 0,
                    "source": "alipay",
                    "note": "未识别到基金代码，请手动补充",
                })

        if not results:
            results.append({
                "error": "未能从截图中识别出基金信息",
                "raw_texts": [t["text"] for t in texts[:10]],
            })

        return results

    def _cluster_by_y(self, texts: List[Dict], tolerance: float = 15) -> List[List[Dict]]:
        """按Y坐标聚类，将同一行的文本归为一组"""
        if not texts:
            return []

        # 计算每个文本块的Y中心
        items = []
        for t in texts:
            box = t["box"]
            y_center = (box[0][1] + box[2][1]) / 2
            x_center = (box[0][0] + box[2][0]) / 2
            items.append({**t, "y_center": y_center, "x_center": x_center})

        # 按Y中心排序
        items.sort(key=lambda x: x["y_center"])

        # 聚类
        clusters = []
        current_cluster = [items[0]]
        for item in items[1:]:
            if abs(item["y_center"] - current_cluster[0]["y_center"]) <= tolerance:
                current_cluster.append(item)
            else:
                # 按X坐标排序
                current_cluster.sort(key=lambda x: x["x_center"])
                clusters.append(current_cluster)
                current_cluster = [item]
        if current_cluster:
            current_cluster.sort(key=lambda x: x["x_center"])
            clusters.append(current_cluster)

        return clusters

    def _parse_tiantian(self, texts: List[Dict]) -> List[Dict]:
        """
        解析同花顺持仓截图

        布局特征：每只基金占2行
        - 第1行：基金名称(左) | 总金额(中) | 持有收益(右，带+/-号)
        - 第2行：基金代码(左) | 日收益(中) | 收益率%(右，带%号)

        采用基于行内相对位置的解析策略：
        1. 先识别基金代码行（6位数字），确定每只基金的Y坐标锚点
        2. 按Y坐标聚类分行
        3. 在每行内部按X坐标排序，按位置顺序提取字段
        """
        # 1. 预处理：提取所有文本块的坐标和内容
        items = []
        for t in texts:
            box = t.get("box") or t.get("position") or t.get("dt_boxes")
            if not box:
                continue
            coords = box
            if isinstance(coords[0], (list, tuple)):
                xs = [p[0] for p in coords]
                ys = [p[1] for p in coords]
                x_center = sum(xs) / len(xs)
                y_center = sum(ys) / len(ys)
                height = max(ys) - min(ys)
            else:
                continue
            text = t.get("text", "").strip()
            if not text:
                continue
            items.append({
                "text": text,
                "x_center": x_center,
                "y_center": y_center,
                "height": height
            })

        if not items:
            return []
        daily_pnl_date = self._extract_daily_pnl_date(texts)

        # OCR原始数据日志
        logger.info(f"同花顺OCR解析开始，共{len(items)}个文本块")
        for i, it in enumerate(items):
            logger.debug(f"  [{i}] text='{it['text']}' x={it['x_center']:.1f} y={it['y_center']:.1f}")

        # 2. 找到所有基金代码（6位数字），作为锚点
        code_pattern = re.compile(r'^\d{6}$')
        code_items = [it for it in items if code_pattern.match(it["text"])]

        if not code_items:
            # 回退：全局搜索基金代码
            all_text = " ".join(t.get("text", "") for t in texts)
            fund_codes = re.findall(r'\b(\d{6})\b', all_text)
            if fund_codes:
                return [{"fund_code": c, "fund_name": f"基金{c}", "shares": 0,
                         "amount": 0, "cost_amount": 0, "source": "tiantian",
                         "daily_pnl": 0, "daily_pnl_date": daily_pnl_date,
                         "note": "请手动补充基金名称和金额"} for c in fund_codes]
            return [{"error": "未能从截图中识别出基金信息",
                     "raw_texts": [t.get("text", "") for t in texts[:15]]}]

        # 按Y坐标排序代码
        code_items.sort(key=lambda x: x["y_center"])

        # 3. 计算行高用于Y坐标聚类
        valid_heights = sorted([it["height"] for it in items if it["height"] > 0])
        median_height = valid_heights[len(valid_heights) // 2] if valid_heights else 30
        y_tolerance = median_height * 1.5  # 同一行的Y容差
        row_gap = median_height * 3.5  # 名称行和代码行之间的最大距离

        logger.info(f"自适应参数: median_height={median_height:.1f}, y_tolerance={y_tolerance:.1f}, row_gap={row_gap:.1f}")

        window_results = self._parse_tiantian_by_code_windows(items, code_items, median_height, daily_pnl_date)
        complete_window_results = [r for r in window_results if r.get("amount", 0) > 0 or r.get("daily_pnl", 0) != 0]
        if complete_window_results and len(complete_window_results) >= max(1, int(len(code_items) * 0.6)):
            logger.info(f"同花顺OCR窗口解析完成，共识别{len(window_results)}只基金")
            for r in window_results:
                logger.info(f"  {r['fund_code']} {r['fund_name']} 金额={r['amount']} 日收益={r.get('daily_pnl', 0)} 收益={r['holding_pnl']} 收益率={r['holding_pnl_pct']}%")
            return window_results

        results = []
        used_item_ids = set()

        for code_item in code_items:
            code = code_item["text"]
            code_y = code_item["y_center"]
            code_x = code_item["x_center"]

            # 4. 找到名称行（代码行上方，Y较小的行）
            # 名称行的Y范围：code_y上方 y_tolerance*0.5 到 row_gap 之间
            name_row_candidates = [it for it in items
                        if (code_y - it["y_center"]) > y_tolerance * 0.5
                        and (code_y - it["y_center"]) < row_gap
                        and id(it) not in used_item_ids]

            # 去重（用id）
            seen_ids = set()
            name_row = []
            for it in name_row_candidates:
                if id(it) not in seen_ids:
                    seen_ids.add(id(it))
                    name_row.append(it)

            # 收集name_row的id集合，用于排除code_row中的重复项
            name_row_ids = {id(it) for it in name_row}

            # 5. 找到代码所在行的其他元素（同一Y水平，排除name_row中的项）
            code_row = [it for it in items
                        if abs(it["y_center"] - code_y) < y_tolerance
                        and id(it) not in used_item_ids
                        and id(it) not in name_row_ids]

            # 名称行按X排序
            name_row.sort(key=lambda x: x["x_center"])
            # 代码行按X排序
            code_row.sort(key=lambda x: x["x_center"])

            logger.debug(f"基金{code}: code_y={code_y:.1f}, name_row=[{', '.join(it['text'] for it in name_row)}], code_row=[{', '.join(it['text'] for it in code_row)}]")

            # 6. 将name_row按Y坐标分为子行（多行名称时，上行=名称+金额+收益，下行=名称续+日收益+收益率）
            fund_name = ""
            amount = 0.0
            holding_pnl = 0.0
            daily_pnl = 0.0
            holding_pnl_pct = 0.0

            # 将name_row按Y聚类为子行（使用更小的容差，因为同一行内Y差距很小）
            name_sub_rows = []
            sub_row_tolerance = median_height * 0.8  # 同一行内的Y差距通常很小
            if name_row:
                name_row_sorted = sorted(name_row, key=lambda x: x["y_center"])
                current_sub = [name_row_sorted[0]]
                for nit in name_row_sorted[1:]:
                    if abs(nit["y_center"] - current_sub[0]["y_center"]) < sub_row_tolerance:
                        current_sub.append(nit)
                    else:
                        current_sub.sort(key=lambda x: x["x_center"])
                        name_sub_rows.append(current_sub)
                        current_sub = [nit]
                if current_sub:
                    current_sub.sort(key=lambda x: x["x_center"])
                    name_sub_rows.append(current_sub)

            # 上行（第一行）：名称 + 金额 + 持有收益
            if name_sub_rows:
                top_row = name_sub_rows[0]
                name_texts = []
                name_numbers = []
                for it in top_row:
                    cleaned = self._clean_amount_text(it["text"])
                    if re.match(r'^[+-]?[\d.]+$', cleaned) and not code_pattern.match(it["text"]):
                        try:
                            name_numbers.append({"value": float(cleaned), "text": it["text"], "x": it["x_center"]})
                        except ValueError:
                            pass
                    elif not code_pattern.match(it["text"]):
                        name_texts.append(it)

                # 基金名称：非数字文本
                if name_texts:
                    name_texts.sort(key=lambda x: x["x_center"])
                    left_x_bound = code_x + 200
                    fund_name = "".join([t["text"] for t in name_texts
                                         if t["x_center"] < left_x_bound])

                # 数字按X排序：第一个是总金额，第二个是持有收益
                name_numbers.sort(key=lambda x: x["x"])
                if len(name_numbers) >= 1:
                    amount = abs(name_numbers[0]["value"])
                if len(name_numbers) >= 2:
                    holding_pnl = name_numbers[1]["value"]

            # 如果有多行名称，第二行包含名称续行 + 日收益 + 收益率
            if len(name_sub_rows) >= 2:
                bottom_row = name_sub_rows[-1]  # 最后一行（最接近代码行）
                for it in bottom_row:
                    text = it["text"].strip()
                    if code_pattern.match(text):
                        continue
                    if "%" in text:
                        pct_match = re.search(r'[+-]?[\d,.]+', text)
                        if pct_match:
                            try:
                                holding_pnl_pct = float(pct_match.group().replace(",", ""))
                            except ValueError:
                                pass
                    else:
                        cleaned = self._clean_amount_text(text)
                        if re.match(r'^[+-]?[\d.]+$', cleaned):
                            try:
                                val = float(cleaned)
                                # 非数字文本跳过
                                if not code_pattern.match(text):
                                    daily_pnl = val
                            except ValueError:
                                pass
                        elif not re.match(r'^[+-]?[\d.]+$', cleaned):
                            # 名称续行
                            if it["x_center"] < code_x + 200:
                                fund_name += text

            # 7. 从代码行提取：日收益(中间数字)、收益率(带%的) —— 仅在步骤6未提取到时补充
            for it in code_row:
                text = it["text"].strip()
                if code_pattern.match(text):
                    continue  # 跳过代码本身
                if "%" in text:
                    if holding_pnl_pct == 0:
                        pct_match = re.search(r'[+-]?[\d,.]+', text)
                        if pct_match:
                            try:
                                holding_pnl_pct = float(pct_match.group().replace(",", ""))
                            except ValueError:
                                pass
                else:
                    cleaned = self._clean_amount_text(text)
                    if re.match(r'^[+-]?[\d.]+$', cleaned) and daily_pnl == 0:
                        try:
                            daily_pnl = float(cleaned)
                        except ValueError:
                            pass

            # 8. 计算成本
            cost_amount = 0.0
            if amount > 0:
                if holding_pnl != 0:
                    cost_amount = round(amount - holding_pnl, 2)
                elif holding_pnl_pct != 0:
                    cost_amount = round(amount * 100 / (100 + holding_pnl_pct), 2)
                else:
                    cost_amount = amount

            # 标记使用过的items
            for it in name_row + code_row:
                used_item_ids.add(id(it))

            results.append({
                "fund_code": code,
                "fund_name": fund_name.strip(),
                "shares": 0,
                "amount": round(amount, 2),
                "cost_amount": round(cost_amount, 2),
                "holding_pnl": round(holding_pnl, 2),
                "holding_pnl_pct": round(holding_pnl_pct, 2),
                "daily_pnl": round(daily_pnl, 2),
                "daily_pnl_date": daily_pnl_date,
                "nav": 0,
                "source": "tiantian",
            })

        logger.info(f"同花顺OCR解析完成，共识别{len(results)}只基金")
        for r in results:
            logger.info(f"  {r['fund_code']} {r['fund_name']} 金额={r['amount']} 日收益={r.get('daily_pnl', 0)} 收益={r['holding_pnl']} 收益率={r['holding_pnl_pct']}%")

        if not results:
            # 回退：全局搜索基金代码
            all_text = " ".join(t.get("text", "") for t in texts)
            fund_codes = re.findall(r'\b(\d{6})\b', all_text)
            for c in fund_codes:
                results.append({
                    "fund_code": c, "fund_name": f"基金{c}", "shares": 0,
                    "amount": 0, "cost_amount": 0, "source": "tiantian",
                    "daily_pnl": 0, "daily_pnl_date": daily_pnl_date,
                    "note": "请手动补充基金名称和金额",
                })

        if not results:
            results.append({
                "error": "未能从截图中识别出基金信息",
                "raw_texts": [t.get("text", "") for t in texts[:15]],
            })

        return results

    def _parse_generic(self, texts: List[Dict]) -> List[Dict]:
        """通用解析：尝试提取基金代码和金额"""
        all_text = " ".join(t["text"] for t in texts)
        fund_codes = re.findall(r'\b(\d{6})\b', all_text)

        results = []
        for code in fund_codes:
            results.append({
                "fund_code": code,
                "fund_name": "",
                "shares": 0,
                "amount": 0,
                "source": "generic",
                "note": "请手动补充基金名称和金额",
            })

        if not results:
            results.append({
                "error": "未能识别到基金代码",
                "raw_texts": [t["text"] for t in texts[:10]],
            })

        return results

    def _parse_tiantian_trades(self, texts: List[Dict]) -> List[Dict]:
        """
        解析同花顺交易记录截图

        同花顺交易记录页布局：
        - 每条交易占两行
        - 第一行：买入/卖出图标 + 基金名称 + 金额(xxx元)或份额(xxx份)
        - 第二行：钱包申购/赎至钱包 + 日期(YYYY-MM-DD HH:MM) + 状态(已撤单)
        - 页面顶部有"全部交易"标题和日期范围筛选
        """
        results = []

        logger.info(f"同花顺交易记录OCR解析开始，共{len(texts)}个文本块")

        # 为每个文本块计算中心坐标
        items = []
        for t in texts:
            box = t["box"]
            y_center = (box[0][1] + box[2][1]) / 2
            x_center = (box[0][0] + box[2][0]) / 2
            items.append({**t, "y_center": y_center, "x_center": x_center})

        for i, it in enumerate(items):
            logger.debug(f"  [{i}] text='{it['text']}' x={it['x_center']:.0f} y={it['y_center']:.0f}")

        # 自适应行高计算
        heights = []
        for t in items:
            box = t.get("box", [])
            if len(box) >= 4:
                h = abs(box[2][1] - box[0][1])
                if h > 0:
                    heights.append(h)
        median_height = sorted(heights)[len(heights) // 2] if heights else 40
        y_tolerance = max(median_height * 0.8, 15)

        logger.info(f"自适应参数: 中位行高={median_height:.0f}, Y聚类容差={y_tolerance:.0f}")

        # 表头过滤关键词
        header_keywords = ["全部交易", "交易进行中", "产品类型", "交易类型", "KB/s"]

        # 过滤表头文本块
        data_items = []
        for it in items:
            text = it["text"].strip()
            if any(kw in text for kw in header_keywords):
                continue
            # 过滤顶部日期范围筛选（含"从""至"）
            if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
                # 独立的纯日期（无时间），可能是筛选条件，跳过
                # 但交易日期带时间，格式为 YYYY-MM-DD HH:MM，不会匹配此规则
                continue
            if text in ["从", "至"]:
                continue
            data_items.append(it)

        # 按Y坐标聚类分行
        if not data_items:
            logger.warning("过滤后无有效文本块")
            return [{"error": "未能从截图中识别出交易信息", "raw_texts": [t["text"] for t in texts[:15]]}]

        data_items.sort(key=lambda x: x["y_center"])
        rows = []
        current_row = [data_items[0]]
        for it in data_items[1:]:
            if abs(it["y_center"] - current_row[0]["y_center"]) <= y_tolerance:
                current_row.append(it)
            else:
                current_row.sort(key=lambda x: x["x_center"])
                rows.append(current_row)
                current_row = [it]
        if current_row:
            current_row.sort(key=lambda x: x["x_center"])
            rows.append(current_row)

        logger.info(f"聚类后共{len(rows)}行")
        for i, row in enumerate(rows):
            row_text = " | ".join(it["text"] for it in row)
            logger.debug(f"  行[{i}] y≈{row[0]['y_center']:.0f}: {row_text}")

        # 基金名称关键词
        fund_keywords = ["混合", "股票", "债券", "ETF", "联接", "指数", "增强", "FOF",
                         "LOF", "QDII", "货币", "纯债", "信用", "转型", "成长",
                         "价值", "优选", "精选", "量化", "科技", "医疗", "消费",
                         "新能源", "芯片", "半导体", "红利", "策略"]

        # 金额/份额匹配模式
        amount_pattern = re.compile(r'([\d,]+\.?\d*)\s*元')
        shares_pattern = re.compile(r'([\d,]+\.?\d*)\s*份')
        date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})')

        # 遍历行，组装交易记录
        # 策略：当某行包含"买入"/"卖出"关键词时，开始一条新记录
        # 后续不含买入/卖出的行归入当前记录
        current_trade = None

        for row in rows:
            row_texts = [it["text"].strip() for it in row]
            row_full = " ".join(row_texts)

            # 判断是否是新交易的起始行（包含买入/卖出标识）
            is_buy = any("买入" in t for t in row_texts)
            is_sell = any("卖出" in t for t in row_texts)

            if is_buy or is_sell:
                # 保存上一条交易
                if current_trade:
                    results.append(current_trade)

                # 开始新交易
                trade_type = "买入" if is_buy else "卖出"
                current_trade = {
                    "trade_type": trade_type,
                    "fund_name": "",
                    "fund_code": "",
                    "amount": 0.0,
                    "shares": 0.0,
                    "trade_date": "",
                    "status": "",
                    "note": "",
                    "source": "ocr_tiantian_trades",
                }

                # 提取基金名称：查找包含基金关键词的文本
                for t in row_texts:
                    if any(kw in t for kw in fund_keywords):
                        # 清理名称（去掉可能混入的买入/卖出）
                        name = t.replace("买入", "").replace("卖出", "").strip()
                        if name:
                            current_trade["fund_name"] = name
                            break

                # 如果没找到关键词匹配的名称，取中间位置的非关键词文本
                if not current_trade["fund_name"]:
                    for t in row_texts:
                        if t not in ["买入", "卖出"] and not amount_pattern.search(t) and not shares_pattern.search(t):
                            if len(t) >= 2 and not re.match(r'^[\d.:]+$', t):
                                current_trade["fund_name"] = t
                                break

                # 提取金额或份额
                for t in row_texts:
                    amt_match = amount_pattern.search(t)
                    if amt_match:
                        val = amt_match.group(1).replace(",", "")
                        try:
                            current_trade["amount"] = float(val)
                        except ValueError:
                            pass
                    shr_match = shares_pattern.search(t)
                    if shr_match:
                        val = shr_match.group(1).replace(",", "")
                        try:
                            current_trade["shares"] = float(val)
                        except ValueError:
                            pass

                # 有时日期也在同一行
                date_match = date_pattern.search(row_full)
                if date_match:
                    current_trade["trade_date"] = date_match.group(1)

            elif current_trade:
                # 非起始行，归入当前交易记录
                # 可能包含：名称续行、日期、状态、申购/赎回描述

                # 名称续行：补充基金名称（如长名称折行）
                for t in row_texts:
                    if any(kw in t for kw in fund_keywords) and current_trade["fund_name"] and t not in current_trade["fund_name"]:
                        # 可能是名称的第二行部分
                        current_trade["fund_name"] += t
                        break

                # 提取日期
                if not current_trade["trade_date"]:
                    date_match = date_pattern.search(row_full)
                    if date_match:
                        current_trade["trade_date"] = date_match.group(1)

                # 提取申购/赎回描述
                for t in row_texts:
                    if "钱包申购" in t or "申购" in t:
                        current_trade["note"] = "钱包申购"
                    elif "赎至钱包" in t or "赎回" in t or "赎至" in t:
                        current_trade["note"] = "赎至钱包"

                # 提取状态
                for t in row_texts:
                    if "已撤单" in t or "已撤回" in t:
                        current_trade["status"] = "已撤单"

                # 如果当前行也有金额/份额（之前没提取到）
                if current_trade["amount"] == 0 and current_trade["shares"] == 0:
                    for t in row_texts:
                        amt_match = amount_pattern.search(t)
                        if amt_match:
                            val = amt_match.group(1).replace(",", "")
                            try:
                                current_trade["amount"] = float(val)
                            except ValueError:
                                pass
                        shr_match = shares_pattern.search(t)
                        if shr_match:
                            val = shr_match.group(1).replace(",", "")
                            try:
                                current_trade["shares"] = float(val)
                            except ValueError:
                                pass

        # 保存最后一条交易
        if current_trade:
            results.append(current_trade)

        # 自动补全note：如果note为空，根据trade_type推断
        for r in results:
            if not r["note"]:
                r["note"] = "钱包申购" if r["trade_type"] == "买入" else "赎至钱包"

        logger.info(f"同花顺交易记录解析完成，共识别{len(results)}条交易")
        for i, r in enumerate(results):
            logger.info(f"  [{i}] {r['trade_type']} {r['fund_name']} "
                        f"金额={r['amount']} 份额={r['shares']} "
                        f"日期={r['trade_date']} 状态={r['status']}")

        if not results:
            return [{"error": "未能从截图中识别出交易信息", "raw_texts": [t["text"] for t in texts[:15]]}]

        return results

    def _lookup_fund_code_by_name(self, fund_name: str) -> str:
        """
        通过基金名称在本地数据库中模糊匹配查找基金代码

        Args:
            fund_name: 基金名称

        Returns:
            基金代码（6位），未找到返回空字符串
        """
        if not fund_name:
            return ""
        try:
            db = SessionLocal()
            try:
                # 精确匹配
                fund = db.query(Fund).filter(Fund.fund_name == fund_name).first()
                if fund:
                    return fund.fund_code

                # 模糊匹配：名称包含关系
                fund = db.query(Fund).filter(Fund.fund_name.like(f"%{fund_name}%")).first()
                if fund:
                    return fund.fund_code

                # 反向模糊：数据库名称被包含在输入名称中
                funds = db.query(Fund).all()
                for f in funds:
                    if f.fund_name and f.fund_name in fund_name:
                        return f.fund_code
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"数据库查询基金代码失败: {e}")
        return ""

    def _fill_fund_codes(self, results: List[Dict]):
        """
        为交易记录批量补全基金代码
        优先从本地数据库匹配，找不到的记录保持fund_code为空
        """
        for item in results:
            if item.get("fund_code"):
                continue
            fund_name = item.get("fund_name", "")
            if not fund_name:
                continue

            code = self._lookup_fund_code_by_name(fund_name)
            if code:
                item["fund_code"] = code
                logger.info(f"基金名称'{fund_name}'匹配到代码: {code}")
            else:
                logger.debug(f"基金名称'{fund_name}'未在本地数据库中找到对应代码")
