import requests
from bs4 import BeautifulSoup
import threading
import csv
import os
import re
import json
import time
from urllib.parse import urljoin, urlparse
import sys
import colorama
from colorama import Fore, Back, Style

colorama.init()


class TGStatCmdParser:
    def __init__(self):
        self.links = []

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'https://tgstat.ru/',
        })

        self.stop_parsing = False

        self.ai_threshold = 20

        self.telegram_enabled = False
        self.telegram_token = ""
        self.telegram_chat_id = ""

    def print_header(self):
        print(f"{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.WHITE}{Style.BRIGHT}          TGSTAT Parser - rxinallday")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")

    def print_status(self, message, status_type="info"):
        prefix = ""
        if status_type == "info":
            prefix = f"{Fore.BLUE}[INFO]{Style.RESET_ALL} "
        elif status_type == "success":
            prefix = f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} "
        elif status_type == "error":
            prefix = f"{Fore.RED}[ERROR]{Style.RESET_ALL} "
        elif status_type == "warning":
            prefix = f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} "
        elif status_type == "progress":
            prefix = f"{Fore.CYAN}[PROGRESS]{Style.RESET_ALL} "

        print(f"{prefix}{message}")

    def configure_telegram(self):
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.WHITE}{Style.BRIGHT}          Telegram Notification Setup")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")

        enable = input("Do you want to enable Telegram notifications? (y/n): ").lower().strip()
        if enable == 'y':
            self.telegram_enabled = True
            self.telegram_token = input("BOT TOKEN: ").strip()
            self.telegram_chat_id = input("CHAT ID: ").strip()
            self.ai_threshold = int(input("Enter AI analysis threshold (% above average): ") or "20")
            self.print_status("Telegram notifications configured successfully!", "success")
        else:
            self.print_status("Telegram notifications disabled", "warning")

    def send_telegram_message(self, message):
        if not self.telegram_enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=payload)
            return response.status_code == 200
        except Exception as e:
            self.print_status(f"Failed to send Telegram message: {str(e)}", "error")
            return False

    def start_parsing(self):
        self.print_header()

        url = input("Enter URL: ").strip()
        if not url:
            self.print_status("No URL provided. Exiting.", "error")
            return

        try:
            max_pages = int(input("Enter maximum number of pages to parse: ") or "50")
        except ValueError:
            max_pages = 50
            self.print_status("Invalid input, using default value: 50 pages", "warning")

        self.links = []
        self.stop_parsing = False

        self.configure_telegram()

        self.print_status(f"Starting to parse URL: {url}", "info")
        self.print_status("Parameters:", "info")
        self.print_status(f"- Maximum pages: {max_pages}", "info")
        self.print_status(f"- Search all links: Enabled", "info")
        self.print_status(f"- Try API request: Enabled", "info")
        self.print_status(f"- Delay: 0.5 seconds", "info")

        try:
            self.parse_url(url, max_pages)
        except KeyboardInterrupt:
            self.print_status("\nParsing stopped by user.", "warning")
            self.stop_parsing = True

        if self.links:
            self.process_results()
        else:
            self.print_status("No Telegram channels found.", "warning")

    def parse_url(self, url, max_pages):
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            delay = 0.5

            current_page = 1
            total_links = 0

            self.print_status("Trying to use API for data retrieval...", "info")

            api_success = self.parse_via_api(url, max_pages, delay)

            if not api_success:
                self.print_status("API failed, switching to regular parsing...", "warning")

                while current_page <= max_pages and not self.stop_parsing:
                    page_url = url
                    if current_page > 1:
                        if "?" in url:
                            page_url = f"{url}&page={current_page}"
                        else:
                            page_url = f"{url}?page={current_page}"

                    self.print_status(f"Processing page {current_page}...", "progress")

                    response = self.session.get(page_url, timeout=30)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, 'html.parser')

                    new_links = self.extract_links_from_soup(soup, base_url)

                    if not new_links and current_page > 1:
                        self.print_status(f"Page {current_page} has no new links. Finishing parsing.", "info")
                        break

                    self.links.extend(new_links)
                    total_links += len(new_links)

                    self.print_status(f"Found {total_links} links (page {current_page})", "success")

                    current_page += 1

                    if current_page <= max_pages and not self.stop_parsing:
                        time.sleep(delay)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.print_status(f"Error: {str(e)}", "error")
            self.print_status(f"Details:\n{error_details}", "error")

    def parse_via_api(self, url, max_pages, delay):
        try:
            category = url.split('/')[-1]

            api_url = f"https://tgstat.ru/channels/list/{category}"

            total_links = 0
            current_page = 1

            while current_page <= max_pages and not self.stop_parsing:
                self.print_status(f"API request: page {current_page}...", "progress")

                params = {
                    'page': current_page,
                    'sort': 'members',
                    'extended': 1
                }

                response = self.session.get(api_url, params=params, timeout=30)

                if response.status_code != 200:
                    self.print_status(f"API returned error: {response.status_code}", "error")
                    return False

                try:
                    data = response.json()
                except:
                    self.print_status("Failed to parse JSON response from API", "error")
                    return False

                if 'items' not in data:
                    self.print_status("API returned unexpected data format", "error")
                    return False

                new_links = []
                for item in data['items']:
                    if 'username' in item and item['username']:
                        username = item['username']
                        title = item.get('title', username)
                        members = item.get('members', 0)

                        new_links.append({
                            'url': f"https://t.me/{username}",
                            'text': title,
                            'members': members,
                            'description': item.get('description', ''),
                            'category': item.get('category', ''),
                            'avg_post_reach': item.get('avg_post_reach', 0),
                            'citations': item.get('citations', 0)
                        })

                if not new_links and current_page > 1:
                    self.print_status(f"API: page {current_page} has no new channels. Finishing.", "info")
                    break

                self.links.extend(new_links)
                total_links += len(new_links)

                self.print_status(f"API: found {total_links} channels (page {current_page})", "success")

                if 'pagination' in data and 'has_next' in data['pagination']:
                    if not data['pagination']['has_next']:
                        self.print_status("API: reached end of list", "info")
                        break

                current_page += 1

                if current_page <= max_pages and not self.stop_parsing:
                    time.sleep(delay)

            return True

        except Exception as e:
            self.print_status(f"Error using API: {str(e)}", "error")
            return False

    def extract_links_from_soup(self, soup, base_url):
        all_links = []

        channel_cards = soup.find_all(class_=["channel-card", "channel-item"])

        if channel_cards:
            self.print_status(f"Found {len(channel_cards)} channel cards", "info")

            for card in channel_cards:
                a_tag = card.find('a', href=True)
                if not a_tag:
                    continue

                href = a_tag.get('href', '')

                if '/channel/' in href:
                    channel_parts = href.split('/')
                    if len(channel_parts) > 1:
                        channel_name = channel_parts[-1]

                        tg_url = f"https://t.me/{channel_name}"

                        title_elem = card.find(class_=["channel-name", "channel-title"])
                        title = title_elem.get_text(strip=True) if title_elem else channel_name

                        members_elem = card.find(class_=["channel-members", "members"])
                        members = members_elem.get_text(strip=True) if members_elem else "Unknown"

                        desc_elem = card.find(class_=["channel-description", "description"])
                        description = desc_elem.get_text(strip=True) if desc_elem else ""

                        cat_elem = card.find(class_=["channel-category", "category"])
                        category = cat_elem.get_text(strip=True) if cat_elem else ""

                        all_links.append({
                            'url': tg_url,
                            'text': title,
                            'members': members,
                            'description': description,
                            'category': category
                        })

        if not all_links:
            a_tags = soup.find_all('a', href=True)

            for a in a_tags:
                href = a.get('href', '')

                if 't.me/' in href or 'telegram.me/' in href:
                    link_text = a.get_text(strip=True)
                    if not link_text:
                        link_text = a.get('title', '') or href

                    all_links.append({
                        'url': href,
                        'text': link_text
                    })
                elif '/channel/' in href:
                    if href.startswith('/'):
                        href = urljoin(base_url, href)

                    channel_parts = href.split('/')
                    if len(channel_parts) > 1:
                        channel_name = channel_parts[-1]
                        tg_url = f"https://t.me/{channel_name}"

                        link_text = a.get_text(strip=True)
                        if not link_text:
                            link_text = a.get('title', '') or channel_name

                        all_links.append({
                            'url': tg_url,
                            'text': link_text
                        })

        if not all_links:
            html_text = str(soup)

            tg_links_pattern = r'(https?://)?(t\.me|telegram\.me)/([a-zA-Z0-9_]+)'
            tg_links = re.findall(tg_links_pattern, html_text)

            for protocol, domain, username in tg_links:
                if not protocol:
                    protocol = "https://"

                full_url = f"{protocol}{domain}/{username}"

                if not any(link['url'] == full_url for link in all_links):
                    all_links.append({
                        'url': full_url,
                        'text': f"@{username}"
                    })

        unique_links = []
        seen_urls = set()

        for link in all_links:
            url = link['url']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_links.append(link)

        return unique_links

    def analyze_channel(self, channel):
        score = 0
        analysis = []

        members = channel.get('members', 0)
        if isinstance(members, str):
            if 'K' in members:
                members = float(members.replace('K', '')) * 1000
            elif 'M' in members:
                members = float(members.replace('M', '')) * 1000000
            else:
                try:
                    members = float(''.join(filter(lambda x: x.isdigit() or x == '.', members)))
                except:
                    members = 0

        if members > 100000:
            score += 30
            analysis.append("Large audience (100K+ subscribers)")
        elif members > 50000:
            score += 25
            analysis.append("Good size audience (50K+ subscribers)")
        elif members > 10000:
            score += 15
            analysis.append("Medium size audience (10K+ subscribers)")
        else:
            score += 5
            analysis.append("Small audience (less than 10K subscribers)")

        avg_reach = channel.get('avg_post_reach', 0)
        if avg_reach > 0:
            engagement_rate = (avg_reach / members) * 100 if members > 0 else 0
            if engagement_rate > 30:
                score += 35
                analysis.append(f"Excellent engagement rate ({engagement_rate:.1f}%)")
            elif engagement_rate > 20:
                score += 25
                analysis.append(f"Very good engagement rate ({engagement_rate:.1f}%)")
            elif engagement_rate > 10:
                score += 15
                analysis.append(f"Good engagement rate ({engagement_rate:.1f}%)")
            else:
                score += 5
                analysis.append(f"Low engagement rate ({engagement_rate:.1f}%)")

        citations = channel.get('citations', 0)
        if citations > 1000:
            score += 20
            analysis.append("Highly cited channel (1000+ citations)")
        elif citations > 500:
            score += 15
            analysis.append("Well cited channel (500+ citations)")
        elif citations > 100:
            score += 10
            analysis.append("Moderately cited channel (100+ citations)")
        elif citations > 0:
            score += 5
            analysis.append("Some citations")

        description = channel.get('description', '')
        if len(description) > 200:
            score += 10
            analysis.append("Detailed channel description")
        elif len(description) > 100:
            score += 7
            analysis.append("Good channel description")
        elif len(description) > 50:
            score += 5
            analysis.append("Basic channel description")
        else:
            analysis.append("Minimal or no description")

        score = min(score, 100)

        return {
            'score': score,
            'analysis': analysis
        }

    def process_results(self):
        if not self.links:
            self.print_status("No Telegram links found.", "warning")
            return

        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.WHITE}{Style.BRIGHT}          Results Analysis")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")

        self.print_status(f"Found {len(self.links)} Telegram channels", "success")

        total_score = 0
        channels_with_scores = []

        for channel in self.links:
            analysis_result = self.analyze_channel(channel)
            channel['analysis'] = analysis_result
            total_score += analysis_result['score']
            channels_with_scores.append(channel)

        avg_score = total_score / len(channels_with_scores) if channels_with_scores else 0
        self.print_status(f"Average channel quality score: {avg_score:.1f}/100", "info")

        channels_with_scores.sort(key=lambda x: x['analysis']['score'], reverse=True)

        print(f"\n{Fore.GREEN}Top 10 channels for advertisers:{Style.RESET_ALL}")
        for i, channel in enumerate(channels_with_scores[:10]):
            score = channel['analysis']['score']
            name = channel['text']
            url = channel['url']
            members = channel.get('members', 'Unknown')

            score_color = Fore.RED
            if score >= 80:
                score_color = Fore.GREEN
            elif score >= 60:
                score_color = Fore.YELLOW

            print(f"{i + 1}. {name} - {score_color}Score: {score:.1f}/100{Style.RESET_ALL}")
            print(f"   URL: {url}")
            print(f"   Subscribers: {members}")
            print(f"   Analysis: {', '.join(channel['analysis']['analysis'])}")
            print()

            if score > (avg_score * (1 + self.ai_threshold / 100)) and self.telegram_enabled:
                percent_above_avg = ((score / avg_score) - 1) * 100
                message = (
                    f"<b>🔥 High-Quality Channel Found!</b>\n\n"
                    f"Channel: <b>{name}</b>\n"
                    f"URL: {url}\n"
                    f"Subscribers: {members}\n"
                    f"Quality Score: {score:.1f}/100 "
                    f"(<b>{percent_above_avg:.1f}%</b> above average)\n\n"
                    f"Analysis:\n"
                    f"- {chr(10).join(channel['analysis']['analysis'])}"
                )

                self.send_telegram_message(message)
                self.print_status(f"Notification sent to Telegram for high-quality channel: {name}", "success")

        self.save_to_csv(channels_with_scores)

    def save_to_csv(self, channels):
        """Save results to CSV"""
        if not channels:
            self.print_status("No data to save", "error")
            return

        try:
            filename = "tgstat_links.csv"
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                # Define fields for CSV
                fieldnames = ['url', 'text', 'members', 'description', 'category', 'quality_score', 'analysis']

                writer = csv.writer(csvfile)
                writer.writerow(fieldnames)

                for channel in channels:
                    writer.writerow([
                        channel.get('url', ''),
                        channel.get('text', ''),
                        channel.get('members', ''),
                        channel.get('description', ''),
                        channel.get('category', ''),
                        channel['analysis'].get('score', 0),
                        '; '.join(channel['analysis'].get('analysis', []))
                    ])

            full_path = os.path.abspath(filename)
            self.print_status(f"Results saved to file: {full_path}", "success")

        except Exception as e:
            self.print_status(f"Failed to save results: {e}", "error")


def main():
    colorama.init()

    try:
        parser = TGStatCmdParser()
        parser.start_parsing()
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
    except Exception as e:
        print(f"\n{Fore.RED}[ERROR] Unexpected error: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
    finally:
        print(Style.RESET_ALL)
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()