from playwright.sync_api import sync_playwright
import time
import csv
import json
from datetime import datetime
import re

# Danh sách ZIP codes cần thử
zip_codes = ["91101", "90001", "10001", "94102", "33101"]


def extract_plan_info_from_html(plan_element, zip_code):
    try:
        html = plan_element.inner_html()
        text = plan_element.inner_text()
        
        plan_info = {
            "zip_code": zip_code,
            "plan_id": "",
            "plan_name": "",
            "plan_type": "",
            "monthly_premium": "",
            "pcp_copay": "",
            "out_of_pocket_max": "",
            "deductible": "",
            "specialist_copay": "",
            "emergency_copay": "",
            "inpatient_hospital": "",
            "tier1_generic_copay": "",
            "services_benefits": ""
        }

        # Plan ID
        plan_id = plan_element.get_attribute("data-planid") or plan_element.get_attribute("data-plan-id")
        if not plan_id:
            plan_id_match = re.search(r'data-planid="([^"]+)"', html)
            if plan_id_match:
                plan_id = plan_id_match.group(1)
        if not plan_id:
            plan_id = f"{zip_code}_{int(time.time() * 1000) % 100000}"
        plan_info["plan_id"] = plan_id

        # Plan Type
        if "bg-pastel-aqua" in html:
            plan_info["plan_type"] = "MA"
        elif "bg-pastel-mint" in html:
            plan_info["plan_type"] = "Medicare Supplement"
        elif "bg-pastel-lavender" in html:
            plan_info["plan_type"] = "PDP"
        else:
            plan_info["plan_type"] = "Unknown"

        # Plan Name (tên nằm đầu text, thường dùng được regex)
        name_match = re.search(r'^([A-Z][^\n$]+)', text)
        if name_match:
            plan_info["plan_name"] = name_match.group(1).strip()

        # Monthly Premium
        premium_match = re.search(r'class="monthly-premium[^"]*".*?<span>\$([\d,.]+)</span>', html)
        if not premium_match:
            premium_match = re.search(r'\$([\d,.]+)[^<]{0,20}(?:monthly|premium)', text, re.IGNORECASE)
        if premium_match:
            plan_info["monthly_premium"] = f"${premium_match.group(1)}"

        # Out-of-pocket Max
        oop_match = re.search(r'(Out[- ]?of[- ]?pocket[^$:\n]*)(?:\$|</span><span>)\$?([\d,]+)', html)
        if oop_match:
            plan_info["out_of_pocket_max"] = f"${oop_match.group(2)}"
        elif "oop-premium-value" in html:
            oop_html_match = re.search(r'class="oop-premium-value[^"]*">\$?([\w]+)', html)
            if oop_html_match:
                plan_info["out_of_pocket_max"] = oop_html_match.group(1)

        # PCP Copay
        pcp_match = re.search(r'(?:PCP|Primary care)[^$:\n]*\$?(\d+(?:\.\d{2})?)', text, re.IGNORECASE)
        if pcp_match:
            plan_info["pcp_copay"] = f"${pcp_match.group(1)}"

        # Specialist Copay
        specialist_match = re.search(r'Specialist[^$\n]*\$?(\d+(?:\.\d{2})?)', text, re.IGNORECASE)
        if specialist_match:
            plan_info["specialist_copay"] = f"${specialist_match.group(1)}"

        # Emergency Copay
        emergency_match = re.search(r'(?:Emergency|ER)[^$\n]*\$?(\d+(?:\.\d{2})?)', text, re.IGNORECASE)
        if emergency_match:
            plan_info["emergency_copay"] = f"${emergency_match.group(1)}"

        # Inpatient Hospital
        inpatient_match = re.search(r'(Inpatient|Hospital)[^$\n]*\$?(\d+(?:\.\d{2})?)', text, re.IGNORECASE)
        if inpatient_match:
            plan_info["inpatient_hospital"] = f"${inpatient_match.group(2)}"

        # Deductible
        deductible_match = re.search(r'(Deductible)[^$\n]*\$?([\d,]+)', text, re.IGNORECASE)
        if deductible_match:
            plan_info["deductible"] = f"${deductible_match.group(2)}"

        # Tier 1 Generic (for PDP)
        tier1_match = re.search(r'Tier\s*1[^$\n]*\$?(\d+(?:\.\d{2})?)', text)
        if not tier1_match:
            tier1_match = re.search(r'Preferred Generic[^$\n]*\$?(\d+(?:\.\d{2})?)', text)
        if tier1_match:
            plan_info["tier1_generic_copay"] = f"${tier1_match.group(1)}"

        # Services / Benefits (thô sơ từ text, chưa phân tích icon)
        benefits_keywords = ['dental', 'vision', 'hearing', 'wellness', 'fitness', 'transportation', 'prescription', 'allowance']
        found_benefits = [word for word in benefits_keywords if word in text.lower()]
        plan_info["services_benefits"] = " | ".join(set(found_benefits))

        print(f"✅ Extracted: {plan_info['plan_name']} ({plan_info['plan_type']}) - Premium: {plan_info['monthly_premium']}")
        return plan_info

    except Exception as e:
        print(f"❌ Error extracting plan info: {e}")
        return None


def extract_plan_info_from_text(plan_element, zip_code):
    """Trích xuất thông tin từ toàn bộ text content của plan card"""
    try:
        plan_info = {
            "zip_code": zip_code,
            "plan_id": "",
            "plan_name": "",
            "plan_type": "",
            "monthly_premium": "",
            "pcp_copay": "",
            "out_of_pocket_max": "",
            "deductible": "",
            "specialist_copay": "",
            "emergency_copay": "",
            "inpatient_hospital": "",
            "tier1_generic_copay": "",
            "services_benefits": ""
        }
        
        # Lấy toàn bộ text content từ plan card
        full_text = plan_element.inner_text()
        print(f"   → Full text preview: {full_text[:200]}...")
        
        # Lấy HTML để phân tích cấu trúc nếu cần
        html_content = plan_element.inner_html()
        
        # 1. Lấy Plan ID từ attributes
        plan_id = plan_element.get_attribute("id")
        if plan_id and "plan-card-" in plan_id:
            plan_info["plan_id"] = plan_id.replace("plan-card-", "")
        else:
            # Thử lấy từ data attributes
            data_plan_id = plan_element.get_attribute("data-plan-id")
            if data_plan_id:
                plan_info["plan_id"] = data_plan_id
            else:
                # Tạo ID từ tên plan nếu không có
                plan_name_match = re.search(r'^([A-Z][^$\n]+?)(?:\s*\$|\n)', full_text, re.MULTILINE)
                if plan_name_match:
                    plan_info["plan_id"] = re.sub(r'[^\w\s-]', '', plan_name_match.group(1))[:50]
        
        # 2. Xác định loại plan từ text
        text_lower = full_text.lower()
        if any(keyword in text_lower for keyword in ['prescription drug', 'pdp', 'drug plan']):
            plan_info["plan_type"] = "PDP"
        elif any(keyword in text_lower for keyword in ['medicare advantage', 'ma plan', 'hmo', 'ppo']):
            plan_info["plan_type"] = "MA"
        elif any(keyword in text_lower for keyword in ['supplement', 'medigap']):
            plan_info["plan_type"] = "Medicare Supplement"
        elif any(keyword in text_lower for keyword in ['special needs', 'snp']):
            plan_info["plan_type"] = "SNP"
        else:
            plan_info["plan_type"] = "Unknown"
        
        # 3. Lấy tên plan - thường ở đầu text
        name_patterns = [
            r'^([A-Z][^$\n]+?)(?:\s*\$|\n)',  # Tên plan ở đầu, kết thúc bằng $ hoặc xuống dòng
            r'([A-Z][^$\n]*(?:Plan|HMO|PPO|PDP)[^$\n]*)',  # Tên có chứa Plan, HMO, PPO, PDP
            r'([A-Z][A-Za-z\s&-]+(?:Medicare|Advantage|Supplement)[A-Za-z\s&-]*)',  # Tên có chứa Medicare keywords
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, full_text, re.MULTILINE)
            if match:
                plan_name = match.group(1).strip()
                if len(plan_name) > 5 and not any(char.isdigit() for char in plan_name[:3]):
                    plan_info["plan_name"] = plan_name
                    break
        
        # 4. Lấy Monthly Premium
        premium_patterns = [
            r'\$(\d+(?:\.\d{2})?)\s*(?:per\s*month|monthly|\/month|\smo)',
            r'Monthly\s*Premium[:\s]*\$(\d+(?:\.\d{2})?)',
            r'Premium[:\s]*\$(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)\s*(?:premium|monthly premium)',
            r'\$(\d+(?:\.\d{2})?)\s*per\s*month',
            r'(\$\d+(?:\.\d{2})?)\s*monthly'
        ]
        
        for pattern in premium_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                if match.group(1).startswith('$'):
                    plan_info["monthly_premium"] = match.group(1)
                else:
                    plan_info["monthly_premium"] = f"${match.group(1)}"
                break
        
        # 5. Lấy Out-of-Pocket Maximum
        oop_patterns = [
            r'Out[- ]of[- ]pocket[^$\n]*\$([0-9,]+)',
            r'Maximum[^$\n]*out[^$\n]*pocket[^$\n]*\$([0-9,]+)',
            r'Annual[^$\n]*out[^$\n]*pocket[^$\n]*\$([0-9,]+)',
            r'OOP[^$\n]*\$([0-9,]+)',
            r'\$([0-9,]+)[^$\n]*out[- ]of[- ]pocket',
            r'(\$[0-9,]+)[^$\n]*(?:maximum|max)[^$\n]*(?:out[- ]of[- ]pocket|oop)'
        ]
        
        for pattern in oop_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                oop_value = match.group(1)
                if not oop_value.startswith('$'):
                    oop_value = f"${oop_value}"
                plan_info["out_of_pocket_max"] = oop_value
                break
        
        # 6. Lấy PCP Copay
        pcp_patterns = [
            r'Primary\s*care[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'PCP[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'Doctor[^$\n]*visit[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'Office[^$\n]*visit[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)[^$\n]*(?:primary care|pcp|doctor visit)',
            r'(\$\d+(?:\.\d{2})?)[^$\n]*copay[^$\n]*(?:primary|pcp|doctor)'
        ]
        
        for pattern in pcp_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                pcp_value = match.group(1)
                if not pcp_value.startswith('$'):
                    pcp_value = f"${pcp_value}"
                plan_info["pcp_copay"] = pcp_value
                break
        
        # 7. Lấy Specialist Copay
        specialist_patterns = [
            r'Specialist[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)[^$\n]*specialist',
            r'(\$\d+(?:\.\d{2})?)[^$\n]*specialist[^$\n]*(?:copay|visit)'
        ]
        
        for pattern in specialist_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                specialist_value = match.group(1)
                if not specialist_value.startswith('$'):
                    specialist_value = f"${specialist_value}"
                plan_info["specialist_copay"] = specialist_value
                break
        
        # 8. Lấy Emergency Copay
        emergency_patterns = [
            r'Emergency[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'ER[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)[^$\n]*emergency',
            r'(\$\d+(?:\.\d{2})?)[^$\n]*emergency[^$\n]*(?:copay|visit)'
        ]
        
        for pattern in emergency_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                emergency_value = match.group(1)
                if not emergency_value.startswith('$'):
                    emergency_value = f"${emergency_value}"
                plan_info["emergency_copay"] = emergency_value
                break
        
        # 9. Lấy Inpatient Hospital
        inpatient_patterns = [
            r'Inpatient[^$\n]*hospital[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'Hospital[^$\n]*stay[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)[^$\n]*(?:inpatient|hospital stay)',
            r'(\$\d+(?:\.\d{2})?)[^$\n]*(?:per day|daily)[^$\n]*hospital'
        ]
        
        for pattern in inpatient_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                inpatient_value = match.group(1)
                if not inpatient_value.startswith('$'):
                    inpatient_value = f"${inpatient_value}"
                plan_info["inpatient_hospital"] = inpatient_value
                break
        
        # 10. Lấy Deductible
        deductible_patterns = [
            r'Deductible[^$\n]*\$([0-9,]+)',
            r'Annual[^$\n]*deductible[^$\n]*\$([0-9,]+)',
            r'\$([0-9,]+)[^$\n]*deductible',
            r'(\$[0-9,]+)[^$\n]*annual[^$\n]*deductible'
        ]
        
        for pattern in deductible_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                deductible_value = match.group(1)
                if not deductible_value.startswith('$'):
                    deductible_value = f"${deductible_value}"
                plan_info["deductible"] = deductible_value
                break
        
        # 11. Lấy Tier 1 Generic Copay (for PDP plans)
        tier1_patterns = [
            r'Tier\s*1[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'Generic[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'Preferred[^$\n]*generic[^$\n]*\$(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)[^$\n]*(?:tier 1|generic|preferred generic)',
            r'(\$\d+(?:\.\d{2})?)[^$\n]*copay[^$\n]*(?:tier 1|generic)'
        ]
        
        for pattern in tier1_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                tier1_value = match.group(1)
                if not tier1_value.startswith('$'):
                    tier1_value = f"${tier1_value}"
                plan_info["tier1_generic_copay"] = tier1_value
                break
        
        # 12. Lấy Services & Benefits
        benefits_list = []
        
        # Tìm các benefits thường gặp
        benefit_patterns = [
            r'(Dental[^.\n]*(?:coverage|benefit|included)[^.\n]*)',
            r'(Vision[^.\n]*(?:coverage|benefit|included)[^.\n]*)',
            r'(Hearing[^.\n]*(?:coverage|benefit|included)[^.\n]*)',
            r'(Wellness[^.\n]*(?:program|benefit|included)[^.\n]*)',
            r'(Fitness[^.\n]*(?:program|benefit|included)[^.\n]*)',
            r'(Transportation[^.\n]*(?:benefit|included)[^.\n]*)',
            r'(Prescription[^.\n]*(?:coverage|benefit|included)[^.\n]*)',
            r'(Medicare[^.\n]*(?:Part A|Part B|Part D)[^.\n]*)',
            r'(\$\d+[^.\n]*(?:allowance|credit|benefit)[^.\n]*)',
            r'([A-Z][^.\n]*(?:included|covered|benefit)[^.\n]*)'
        ]
        
        for pattern in benefit_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                benefit_text = match.strip()
                if (len(benefit_text) > 10 and 
                    benefit_text not in benefits_list and 
                    any(keyword in benefit_text.lower() for keyword in ['dental', 'vision', 'hearing', 'wellness', 'fitness', 'transportation', 'prescription', 'allowance', 'credit', 'included', 'covered'])):
                    benefits_list.append(benefit_text)
        
        # Gộp benefits thành chuỗi
        if benefits_list:
            plan_info["services_benefits"] = " | ".join(benefits_list[:5])  # Chỉ lấy 5 benefits đầu
        
        # Debug: In ra thông tin đã trích xuất
        print(f"     → Plan ID: {plan_info['plan_id']}")
        print(f"     → Name: {plan_info['plan_name']}")
        print(f"     → Type: {plan_info['plan_type']}")
        print(f"     → Premium: {plan_info['monthly_premium']}")
        print(f"     → PCP: {plan_info['pcp_copay']}")
        print(f"     → OOP Max: {plan_info['out_of_pocket_max']}")
        
        return plan_info
        
    except Exception as e:
        print(f"   → Lỗi extract plan info: {e}")
        return None

def save_to_csv(all_plans_data, filename="uhc_medicare_plans_text_extraction.csv"):
    """Lưu dữ liệu vào file CSV"""
    if not all_plans_data:
        print("Không có dữ liệu để lưu")
        return
    
    headers = [
        "zip_code",
        "plan_type", 
        "plan_id",
        "plan_name",
        "monthly_premium",
        "pcp_copay",
        "out_of_pocket_max",
        "deductible",
        "specialist_copay",
        "emergency_copay",
        "inpatient_hospital",
        "tier1_generic_copay",
        "services_benefits"
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for plan in all_plans_data:
            writer.writerow(plan)
    
    print(f"✅ Đã lưu {len(all_plans_data)} plans vào {filename}")

def main():
    all_plans_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Thiết lập user agent
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

        for zip_code in zip_codes:
            try:
                print(f"\n{'='*60}")
                print(f"=== Xử lý ZIP code: {zip_code} ===")
                print('='*60)
                
                # Bước 1: Truy cập trang chính và nhập ZIP
                print("1. Truy cập trang UHC Medicare...")
                page.goto("https://www.uhc.com/medicare", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(3)
                
                # Đóng popup nếu có
                try:
                    popup_selectors = [
                        '[aria-label="Close"]',
                        '.close',
                        '.modal-close',
                        'button:has-text("Close")',
                        'button:has-text("×")'
                    ]
                    for selector in popup_selectors:
                        try:
                            popup_close = page.locator(selector).first
                            if popup_close.is_visible():
                                popup_close.click()
                                time.sleep(1)
                                break
                        except:
                            continue
                except:
                    pass
                
                # Nhập ZIP code
                print("2. Nhập ZIP code...")
                zip_selectors = [
                    "#zipcodemeded-0",
                    'input[name="zipcodemeded-0"]',
                    'input[placeholder*="ZIP"]',
                    'input[type="tel"]',
                    'input[maxlength="5"]'
                ]
                
                zip_input = None
                for selector in zip_selectors:
                    try:
                        element = page.locator(selector).first
                        if element.is_visible():
                            zip_input = element
                            break
                    except:
                        continue
                
                if not zip_input:
                    print("❌ Không tìm thấy ô nhập ZIP")
                    continue
                
                zip_input.clear()
                zip_input.fill(zip_code)
                time.sleep(1)
                
                # Click View Plans
                print("3. Click View Plans...")
                button_selectors = [
                    'button.uhc-zip-button-primary',
                    'button.uhc-zip-button',
                    'button:has-text("View plans")',
                    'button:has-text("View")',
                    'input[type="submit"]'
                ]
                
                submit_button = None
                for selector in button_selectors:
                    try:
                        element = page.locator(selector).first
                        if element.is_visible():
                            submit_button = element
                            break
                    except:
                        continue
                
                if not submit_button:
                    print("❌ Không tìm thấy nút View Plans")
                    continue
                
                submit_button.click()
                
                # Chờ navigation
                print("4. Chờ trang kết quả...")
                try:
                    page.wait_for_function(
                        "() => window.location.href.includes('plan-summary') || document.querySelector('[id*=\"plan-card-\"]') || document.querySelector('.plan-card')", 
                        timeout=30000
                    )
                except:
                    page.wait_for_load_state("networkidle", timeout=20000)
                
                time.sleep(5)
                
                # Bước 2: Tìm và extract tất cả plan cards
                print("5. Tìm các plan cards...")
                
                # Thử nhiều selector để tìm plan cards
                plan_card_selectors = [
                    '[id*="plan-card-"]',
                    '.plan-card',
                    '[class*="plan-card"]',
                    '[data-plan-id]',
                    '[aria-label*="plan"]',
                    'div[class*="card"]:has-text("$")',  # Div có class chứa "card" và có text "$"
                    'article',
                    'section[class*="plan"]'
                ]
                
                plan_cards = []
                for selector in plan_card_selectors:
                    try:
                        cards = page.locator(selector).all()
                        if cards:
                            plan_cards = cards
                            print(f"   → Tìm thấy {len(cards)} plan cards bằng selector: {selector}")
                            break
                    except:
                        continue
                
                if not plan_cards:
                    print("❌ Không tìm thấy plan cards")
                    # Debug: In ra HTML để kiểm tra
                    print("Debug: In ra HTML structure...")
                    body_html = page.locator('body').inner_html()
                    print(f"HTML preview: {body_html[:1000]}...")
                    continue
                
                # Extract thông tin từ mỗi plan card
                for i, card in enumerate(plan_cards):
                    try:
                        print(f"\n   → Xử lý plan card {i+1}/{len(plan_cards)}")
                        
                        # Lấy toàn bộ text để debug
                        card_text = card.inner_text()
                        if len(card_text) < 50:  # Skip cards with too little content
                            print(f"     ⚠ Skipping card with insufficient content: {card_text}")
                            continue
                        
                        plan_info = extract_plan_info_from_html(card, zip_code)
                        
                        if plan_info and (plan_info["plan_id"] or plan_info["plan_name"]):
                            # Tạo unique ID nếu chưa có
                            if not plan_info["plan_id"]:
                                plan_info["plan_id"] = f"{zip_code}_{i+1}"
                            
                            # Kiểm tra duplicate
                            if not any(p["plan_id"] == plan_info["plan_id"] for p in all_plans_data):
                                all_plans_data.append(plan_info)
                                print(f"     ✓ Đã thêm: {plan_info['plan_name'][:50]}...")
                            else:
                                print(f"     ⚠ Duplicate plan ID: {plan_info['plan_id']}")
                        else:
                            print(f"     ✗ Không lấy được thông tin plan")
                            
                    except Exception as e:
                        print(f"     ✗ Lỗi xử lý plan card {i+1}: {e}")
                        continue
                
                # Thử scroll và load thêm plans
                print("\n6. Thử scroll để load thêm plans...")
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(3)
                    
                    # Tìm và click load more buttons
                    load_more_selectors = [
                        'button:has-text("Load more")',
                        'button:has-text("Show more")',
                        'button:has-text("View more")',
                        '.load-more',
                        '.show-more'
                    ]
                    
                    for selector in load_more_selectors:
                        try:
                            button = page.locator(selector).first
                            if button.is_visible():
                                button.click()
                                time.sleep(3)
                                print("   → Clicked load more button")
                                break
                        except:
                            continue
                    
                except Exception as e:
                    print(f"   → Lỗi scroll/load more: {e}")
                
                print(f"✅ Hoàn thành ZIP {zip_code}: {len([p for p in all_plans_data if p['zip_code'] == zip_code])} plans")
                
            except Exception as e:
                print(f"❌ Lỗi với ZIP {zip_code}: {e}")
                continue

        browser.close()
    
    # Lưu kết quả
    print(f"\n{'='*70}")
    print("=== LƯU KẾT QUẢ ===")
    print('='*70)
    
    if all_plans_data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"uhc_medicare_plans_text_extraction_{timestamp}.csv"
        save_to_csv(all_plans_data, csv_filename)
        
        # Lưu JSON với full text để debug
        json_filename = f"uhc_medicare_plans_text_extraction_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(all_plans_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Đã lưu JSON backup: {json_filename}")
        
        # Thống kê
        print(f"\n{'='*70}")
        print("=== THỐNG KÊ ===")
        print('='*70)
        print(f"Tổng số plans: {len(all_plans_data)}")
        
        # Thống kê theo ZIP
        zip_stats = {}
        for plan in all_plans_data:
            zip_code = plan["zip_code"]
            if zip_code not in zip_stats:
                zip_stats[zip_code] = 0
            zip_stats[zip_code] += 1
        
        print("\nTheo ZIP code:")
        for zip_code, count in zip_stats.items():
            print(f"  ZIP {zip_code}: {count} plans")
        
        # Hiển thị sample data
        print(f"\n{'='*70}")
        print("=== SAMPLE DATA ===")
        print('='*70)
        for i, plan in enumerate(all_plans_data[:2]):
            print(f"\nPlan {i+1}:")
            for key, value in plan.items():
                if value:
                    print(f"  {key}: {value}")
            
    else:
        print("❌ Không có dữ liệu nào được thu thập")

if __name__ == "__main__":
    main()