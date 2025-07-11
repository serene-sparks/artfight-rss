"""ArtFight API client for scraping profile data and team standings."""

import asyncio
import html
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin
from collections.abc import Sequence

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl, parse_obj_as

from .cache import RateLimiter
from .config import settings
from .database import ArtFightDatabase
from .logging_config import get_logger
from .models import ArtFightAttack, ArtFightDefense, TeamStanding

# Set up logging
logger = get_logger(__name__)

# Constants
REMEMBER_WEB_COOKIE_SUFFIX = "59ba36addc2b2f9401580f014c7f58ea4e30989d"


class ArtFightClient:
    """Client for interacting with ArtFight."""

    def __init__(self, rate_limiter: RateLimiter, database: ArtFightDatabase) -> None:
        """Initialize ArtFight client."""
        self.base_url = settings.artfight_base_url
        self.rate_limiter = rate_limiter
        self.database = database

        # Authentication validation cache (5 minutes)
        self._auth_cache = {
            'is_valid': None,
            'last_check': None,
            'cache_duration': timedelta(minutes=5)
        }

        logger.info(f"Initializing ArtFight client with base URL: {self.base_url}")

        # Set up headers to match the working test exactly
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }

        logger.debug(f"Request headers: {headers}")

        # Add authentication cookies if provided
        self.cookies = {}
        if settings.laravel_session:
            self.cookies["laravel_session"] = settings.laravel_session
        if settings.cf_clearance:
            self.cookies["cf_clearance"] = settings.cf_clearance
        if settings.remember_web:
            self.cookies[f"remember_web_{REMEMBER_WEB_COOKIE_SUFFIX}"] = settings.remember_web

        logger.debug(f"Cookies configured: {list(self.cookies.keys())}")

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers=headers,
            cookies=self.cookies
        )

        logger.info("ArtFight client initialized successfully")

    def _log_request(self, method: str, url: str, **kwargs) -> None:
        """Log HTTP request details."""
        logger.debug(f"HTTP {method.upper()} request to: {url}")
        if 'cookies' in kwargs and kwargs['cookies']:
            cookie_info = {}
            for key, value in kwargs['cookies'].items():
                if key in ['laravel_session', 'cf_clearance', f"remember_web_{REMEMBER_WEB_COOKIE_SUFFIX}"]:
                    # Show first and last few characters for security
                    if len(value) > 8:
                        cookie_info[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    cookie_info[key] = value
            logger.debug(f"Request cookies: {cookie_info}")
        if 'headers' in kwargs and kwargs['headers']:
            logger.debug(f"Request headers: {dict(kwargs['headers'])}")

    def _log_response(self, response: httpx.Response) -> None:
        """Log HTTP response details."""
        logger.debug(f"HTTP response: {response.status_code} {response.reason_phrase}")
        logger.debug(f"Response URL: {response.url}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        if response.cookies:
            cookie_info = {}
            for key, value in response.cookies.items():
                if key in ['laravel_session', 'cf_clearance', f"remember_web_{REMEMBER_WEB_COOKIE_SUFFIX}"]:
                    # Show first and last few characters for security
                    if len(value) > 8:
                        cookie_info[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    cookie_info[key] = value
            logger.debug(f"Response cookies: {cookie_info}")

            # Only refresh cookies on successful responses (200)
            if response.status_code == 200:
                self._refresh_cookies_from_response(response)
            else:
                # Log but don't refresh on non-200 responses
                if 'laravel_session' in response.cookies:
                    logger.debug("New Laravel session cookie received but not refreshed (non-200 response)")
                if 'cf_clearance' in response.cookies:
                    logger.debug("New CF clearance cookie received but not refreshed (non-200 response)")

        # Log redirect chain if any
        if response.history:
            logger.debug("Redirect chain:")
            for hist_response in response.history:
                logger.debug(f"  {hist_response.status_code} -> {hist_response.url}")
            logger.debug(f"  Final: {response.status_code} -> {response.url}")

    def _refresh_cookies_from_response(self, response: httpx.Response) -> None:
        """Refresh cookies from a successful response."""
        if not response.cookies:
            return

        cookies_updated = False

        # Update Laravel session cookie
        if 'laravel_session' in response.cookies:
            new_session = response.cookies['laravel_session']
            if new_session != self.cookies.get('laravel_session'):
                self.cookies['laravel_session'] = new_session
                cookies_updated = True
                logger.info(f"Updated Laravel session cookie: {new_session[:4]}...{new_session[-4:]}")

        # Update CF clearance cookie
        if 'cf_clearance' in response.cookies:
            new_clearance = response.cookies['cf_clearance']
            if new_clearance != self.cookies.get('cf_clearance'):
                self.cookies['cf_clearance'] = new_clearance
                cookies_updated = True
                logger.info(f"Updated CF clearance cookie: {new_clearance[:4]}...{new_clearance[-4:]}")

        # Update remember web cookie
        if f"remember_web_{REMEMBER_WEB_COOKIE_SUFFIX}" in response.cookies:
            new_remember = response.cookies[f"remember_web_{REMEMBER_WEB_COOKIE_SUFFIX}"]
            if new_remember != self.cookies.get(f"remember_web_{REMEMBER_WEB_COOKIE_SUFFIX}"):
                self.cookies[f"remember_web_{REMEMBER_WEB_COOKIE_SUFFIX}"] = new_remember
                cookies_updated = True
                logger.info(f"Updated remember web cookie: {new_remember[:4]}...{new_remember[-4:]}")

        if cookies_updated:
            # Update the httpx client with new cookies
            self.client.cookies.update(self.cookies)
            logger.info("Client cookies updated successfully")

            # Clear authentication cache since cookies changed
            self.clear_auth_cache()

    async def _fetch_user_content(self, username: str, content_type: str) -> Sequence[ArtFightAttack | ArtFightDefense]:
        """Shared method for fetching attacks or defenses with pagination."""
        logger.info(f"Fetching {content_type} for user: {username}")

        # Check rate limit
        if not self.rate_limiter.can_request(f"{content_type}_{username}"):
            logger.info(f"Rate limited for {content_type}_{username}, returning existing data from database.")
            if content_type == "attacks":
                return self.database.get_attacks_for_users([username])
            else:
                return self.database.get_defenses_for_users([username])

        try:
            if settings.laravel_session and not await self.validate_authentication():
                logger.warning(f"Authentication failed for {content_type} - session may be invalid.")
                return []

            all_items: list[ArtFightAttack | ArtFightDefense] = []
            page = 1
            base_url = urljoin(self.base_url, f"/~{username}/{content_type}")

            while True:
                page_url = f"{base_url}?page={page}"
                logger.debug(f"Fetching {content_type} page {page}: {page_url}")

                response = await self.client.get(page_url)
                self._log_response(response)
                response.raise_for_status()

                if content_type == "attacks":
                    page_items = self._parse_attacks_from_html(response.text, username)
                    existing_ids = self.database.get_existing_attack_ids(username)
                else:
                    page_items = self._parse_defenses_from_html(response.text, username)
                    existing_ids = self.database.get_existing_defense_ids(username)
                
                if not page_items:
                    break

                new_items = [item for item in page_items if item.id not in existing_ids]
                all_items.extend(page_items)

                if not new_items and page > 1:
                    break

                if not self._has_next_page(response.text):
                    break

                page += 1
                await asyncio.sleep(self._calculate_page_delay())

            # Save all fetched items to database
            if all_items:
                if content_type == "attacks":
                    attacks = [item for item in all_items if isinstance(item, ArtFightAttack)]
                    if attacks:
                        self.database.save_attacks(attacks)
                        logger.debug(f"Saved {len(attacks)} attacks to database for {username}")
                elif content_type == "defenses":  # defenses
                    defenses = [item for item in all_items if isinstance(item, ArtFightDefense)]
                    if defenses:
                        self.database.save_defenses(defenses)
                        logger.debug(f"Saved {len(defenses)} defenses to database for {username}")
                else:
                    raise ValueError(f"Invalid content type: {content_type}")

            return all_items
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {content_type} for {username}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching {content_type} for {username}: {e}")
            return []

    async def validate_authentication(self) -> bool:
        """Validate authentication by checking a protected page."""
        if not settings.laravel_session:
            logger.debug("No Laravel session configured, skipping authentication validation")
            return False

        # Check if we have a valid cached result
        now = datetime.now(UTC)
        if (self._auth_cache['last_check'] and
            self._auth_cache['is_valid'] is not None and
            now - self._auth_cache['last_check'] < self._auth_cache['cache_duration']):

            logger.debug(f"Using cached authentication result: {self._auth_cache['is_valid']} (cached {now - self._auth_cache['last_check']} ago)")
            return self._auth_cache['is_valid']

        # Cache expired or no cache, perform actual validation
        logger.debug("Authentication cache expired or missing, performing validation")

        try:
            # Try to access a page that requires authentication
            # ArtFight's profile page or dashboard would be good for this
            test_url = urljoin(self.base_url, "/~fourleafisland/defenses")
            logger.debug("Validating authentication by accessing protected page")
            self._log_request("GET", test_url, cookies=self.cookies)

            response = await self.client.get(test_url)
            self._log_response(response)

            # Check if we're redirected to login or get an error
            if response.status_code == 302:
                # Redirected to login page
                logger.warning("Authentication validation failed: redirected to login page")
                self._auth_cache['is_valid'] = False
                self._auth_cache['last_check'] = now
                return False
            elif response.status_code == 200:
                # Check if the page contains login elements (indicating we're not logged in)
                soup = BeautifulSoup(response.text, "html.parser")
                login_elements = soup.find_all("a", href="/login") or soup.find_all("form", action="/login")
                is_authenticated = len(login_elements) == 0
                logger.debug(f"Authentication validation result: {'success' if is_authenticated else 'failed'} (login elements found: {len(login_elements)})")

                # Cache the result
                self._auth_cache['is_valid'] = is_authenticated
                self._auth_cache['last_check'] = now

                return is_authenticated
            else:
                logger.warning(f"Authentication validation failed: unexpected status code {response.status_code}")
                self._auth_cache['is_valid'] = False
                self._auth_cache['last_check'] = now
                return False

        except Exception as e:
            logger.error(f"Error validating authentication: {e}")
            self._auth_cache['is_valid'] = False
            self._auth_cache['last_check'] = now
            return False

    def get_authentication_info(self) -> dict:
        """Get information about the current authentication status."""
        return {
            "authenticated": bool(settings.laravel_session),
            "laravel_session_configured": bool(settings.laravel_session),
            "cf_clearance_configured": bool(settings.cf_clearance),
            "laravel_session_length": len(settings.laravel_session) if settings.laravel_session else 0,
            "cf_clearance_length": len(settings.cf_clearance) if settings.cf_clearance else 0,
            "current_cookies": {
                "laravel_session": f"{self.cookies.get('laravel_session', '')[:4]}...{self.cookies.get('laravel_session', '')[-4:]}" if self.cookies.get('laravel_session') else None,
                "cf_clearance": f"{self.cookies.get('cf_clearance', '')[:4]}...{self.cookies.get('cf_clearance', '')[-4:]}" if self.cookies.get('cf_clearance') else None
            },
            "auth_cache": {
                "is_valid": self._auth_cache['is_valid'],
                "last_check": self._auth_cache['last_check'],
                "cache_duration": str(self._auth_cache['cache_duration'])
            }
        }

    def clear_auth_cache(self) -> None:
        """Clear the authentication validation cache."""
        self._auth_cache['is_valid'] = None
        self._auth_cache['last_check'] = None
        logger.debug("Authentication cache cleared")

    def _calculate_page_delay(self) -> float:
        """Calculate delay for page requests with wobble."""
        import random

        base_delay = settings.page_request_delay_sec
        wobble_factor = settings.page_request_wobble

        # Calculate random wobble (±wobble_factor)
        wobble = random.uniform(-wobble_factor, wobble_factor)
        actual_delay = base_delay * (1 + wobble)

        # Ensure delay is not negative
        actual_delay = max(0.1, actual_delay)

        logger.debug(f"Page delay: {base_delay}s base + {wobble:+.2f} wobble = {actual_delay:.2f}s")
        return actual_delay

    def _parse_attacks_from_html(self, html: str, username: str) -> list[ArtFightAttack]:
        """Parse attacks from HTML content."""
        elements = self._parse_attack_defense_elements(html, username, is_defense=False)
        return [elem for elem in elements if isinstance(elem, ArtFightAttack)]

    def _parse_defenses_from_html(self, html: str, username: str) -> list[ArtFightDefense]:
        """Parse defenses from HTML content."""
        elements = self._parse_attack_defense_elements(html, username, is_defense=True)
        return [elem for elem in elements if isinstance(elem, ArtFightDefense)]

    def _parse_attack_defense_elements(self, html: str, username: str, is_defense: bool) -> list[ArtFightAttack | ArtFightDefense]:
        """Shared parsing function for both attacks and defenses."""
        soup = BeautifulSoup(html, "html.parser")
        elements = []

        # Find all <a> elements with class 'attack-thumb' (ArtFight attack/defense thumbnails)
        thumb_elements = soup.find_all("a", class_="attack-thumb")
        logger.debug(f"Found {len(thumb_elements)} {'defense' if is_defense else 'attack'} thumbnails for user {username}")

        for i, element in enumerate(thumb_elements):
            try:
                logger.debug(f"Parsing {'defense' if is_defense else 'attack'} element {i+1}/{len(thumb_elements)}")
                parsed_element = self._parse_attack_defense_element(element, username, is_defense)
                if parsed_element:
                    elements.append(parsed_element)
                    logger.debug(f"Successfully parsed {'defense' if is_defense else 'attack'}: {parsed_element.title}")
                else:
                    logger.debug(f"Failed to parse {'defense' if is_defense else 'attack'} element {i+1}")
            except Exception as e:
                logger.error(f"Error parsing {'defense' if is_defense else 'attack'} element {i+1}: {e}")
                continue

        logger.debug(f"Successfully parsed {len(elements)} {'defenses' if is_defense else 'attacks'} for user {username}")
        return elements

    def _parse_attack_element(self, element, username: str) -> ArtFightAttack | None:
        """Parse a single attack element from a <a> tag."""
        result = self._parse_attack_defense_element(element, username, is_defense=False)
        return result if isinstance(result, ArtFightAttack) else None

    def _parse_defense_element(self, element, username: str) -> ArtFightDefense | None:
        """Parse a single defense element from a <a> tag."""
        result = self._parse_attack_defense_element(element, username, is_defense=True)
        return result if isinstance(result, ArtFightDefense) else None

    def _parse_attack_defense_element(self, element, username: str, is_defense: bool) -> ArtFightAttack | ArtFightDefense | None:
        """Parse a single attack or defense element from a <a> tag."""
        try:
            # Extract ID from data-id or from the URL
            element_id = element.get("data-id")
            if not element_id:
                # Try to extract from the href
                href = element.get("href", "")
                # e.g. /attack/9390471.office-girlsss
                match = re.search(r"/attack/(\\d+)", href)
                if match:
                    element_id = match.group(1)
                else:
                    element_id = href

            # Extract link
            link = urljoin(self.base_url, element.get("href", ""))
            url_http = parse_obj_as(HttpUrl, link)

            # Extract image
            img_elem = element.find("img")
            image_url_http = None
            if img_elem and img_elem.get("src"):
                image_url = img_elem["src"]
                # If the image URL is absolute, use as is; otherwise, join with base_url
                if image_url.startswith("http"):
                    image_url_http = parse_obj_as(HttpUrl, image_url)
                else:
                    image_url_http = parse_obj_as(HttpUrl, urljoin(self.base_url, image_url))

            # Extract title from title on the <img> tag
            # Can be misleading: popper moves the data to data-original-title in a browser
            title = None
            if img_elem and img_elem.get("title"):
                title = html.unescape(img_elem["title"])
            if not title:
                # Fallback: use alt attribute or default
                alt_text = img_elem.get("alt") if img_elem and img_elem.get("alt") else f"Untitled {'Defense' if is_defense else 'Attack'}"
                title = html.unescape(alt_text)

            # TODO: load from the attack page
            description = None

            # Parse title to extract attacker/defender information
            # Title format is typically "Title by Username" for defenses
            # For attacks, the logic is reversed
            if " by " in title:
                title_part, user_part = title.split(" by ", 1)
                title = title_part.strip()
                other_user = user_part.strip()
            else:
                other_user = "Unknown"

            fetched_at = datetime.now(UTC)

            if is_defense:
                # For defenses: profile owner is defender, title contains attacker
                defender = username
                attacker = other_user

                return ArtFightDefense(
                    id=element_id,
                    title=title,
                    description=description,
                    image_url=image_url_http,
                    defender_user=defender,
                    attacker_user=attacker,
                    fetched_at=fetched_at,
                    url=url_http
                )
            else:
                # For attacks: profile owner is attacker, title contains attacker
                # FIXME: Need to parse the attack page to get the defender
                attacker = username
                defender = "TODO"

                return ArtFightAttack(
                    id=element_id,
                    title=title,
                    description=description,
                    image_url=image_url_http,
                    attacker_user=attacker,
                    defender_user=defender,
                    fetched_at=fetched_at,
                    url=url_http
                )

        except Exception as e:
            print(f"Error parsing {'defense' if is_defense else 'attack'} element: {e}")
            return None

    def _has_next_page(self, html: str) -> bool:
        """Check if there's a next page by looking for disabled 'Next' button."""
        soup = BeautifulSoup(html, "html.parser")

        # Look for the "Next" button
        next_button = soup.find("a", class_="page-link", attrs={"aria-label": "Next »"})

        if next_button:
            # Check if the button is disabled by looking for disabled class
            is_disabled = "disabled" in str(next_button)
            logger.debug(f"Found Next button, disabled: {is_disabled}")
            return not is_disabled

        # If no Next button found, assume we're on the last page
        logger.debug("No Next button found, assuming last page")
        return False

    async def get_team_standings(self) -> list[TeamStanding]:
        """Get current team standings."""
        # Check rate limit
        if not self.rate_limiter.can_request("teams"):
            # Return existing data from database if rate limited
            logger.info("Rate limited for teams, returning existing standings from database")
            return self.database.get_team_standings()

        try:
            # Check authentication first if session cookie is provided
            if settings.laravel_session and not await self.validate_authentication():
                logger.warning("Authentication failed for team standings - session cookie may be invalid")
                return []

            # Fetch event page (contains both progress bars and detailed metrics)
            event_url = urljoin(self.base_url, "/event")
            logger.info("Fetching team standings from event page")
            self._log_request("GET", event_url, cookies=self.cookies)

            response = await self.client.get(event_url)
            self._log_response(response)
            response.raise_for_status()

            # Parse team standings from the page
            logger.debug(f"Parsing team standings from HTML (content length: {len(response.text)})")
            standings = self._parse_team_standings_from_html(response.text)

            # Save standings to database
            if standings:
                self.database.save_team_standings(standings)

            # Record the request
            self.rate_limiter.record_request("teams")

            logger.info(f"Successfully fetched {len(standings)} team standings")
            return standings

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching team standings: {e}")
            # Try to get response from the exception
            try:
                response = getattr(e, 'response', None)
                if response:
                    self._log_response(response)
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching team standings: {e}")
            return []

    def _parse_team_standings_from_html(self, html: str) -> list[TeamStanding]:
        """Parse team standings from HTML content."""
        soup = BeautifulSoup(html, "html.parser")
        standings = []

        # Look for the progress bar that contains team standings
        progress_div = soup.find("div", class_="progress")
        if not progress_div or not isinstance(progress_div, Tag):
            logger.warning("No progress bar found for team standings")
            logger.warning(f"HTML: {html}")
            return standings

        # Find all progress bars within the main progress div
        progress_bars = progress_div.find_all("div", class_="progress-bar")
        if not progress_bars or len(progress_bars) != 2:
            logger.warning(f"Expected 2 progress bars, found {len(progress_bars) if progress_bars else 0}")
            return standings

        logger.debug(f"Found {len(progress_bars)} progress bars for team standings")

        # Use team colors to determine which bar corresponds to which team
        team1_percentage = self._parse_team_percentage_by_color(progress_bars)
        if team1_percentage is not None:
            fetched_at = datetime.now(UTC)

            # Parse detailed team metrics from the event page
            team_metrics = self._parse_team_metrics_from_html(html)

            standing = TeamStanding(
                team1_percentage=team1_percentage,
                fetched_at=fetched_at,
                leader_change=False,  # Will be set by database logic
                **team_metrics
            )
            standings.append(standing)
            logger.debug(f"Parsed team standings: Team 1 = {team1_percentage:.2f}%, Team 2 = {100-team1_percentage:.2f}%")

        return standings

    def _parse_team_percentage_by_color(self, progress_bars) -> float | None:
        """Parse team percentage using team colors to determine which bar is which team."""
        try:
            if not settings.teams:
                logger.warning("No team colors configured, falling back to first bar as team1")
                return self._parse_team1_percentage(progress_bars[0])

            team1_color = settings.teams.team1.color
            team2_color = settings.teams.team2.color

            logger.debug(f"Looking for team colors: Team1={team1_color}, Team2={team2_color}")

            team1_percentage = None
            team2_percentage = None

            for bar in progress_bars:
                bg_color = self._extract_background_color(bar)
                if not bg_color:
                    continue

                width_percent = self._extract_width_percentage(bar)
                if width_percent is None:
                    continue

                # Match color to team
                if bg_color.lower() == team1_color.lower():
                    team1_percentage = width_percent
                    logger.debug(f"Team1 ({settings.teams.team1.name}) percentage: {width_percent:.2f}%")
                elif bg_color.lower() == team2_color.lower():
                    team2_percentage = width_percent
                    logger.debug(f"Team2 ({settings.teams.team2.name}) percentage: {width_percent:.2f}%")
                else:
                    logger.warning(f"Unknown team color: {bg_color}")

            # Return team1 percentage (the one we store in the database)
            if team1_percentage is not None:
                return team1_percentage
            elif team2_percentage is not None:
                # If we only found team2, calculate team1 percentage
                return 100 - team2_percentage

            logger.warning("Could not determine team percentages from colors")
            return None

        except Exception as e:
            logger.error(f"Error parsing team percentage by color: {e}")
            return None

    def _extract_background_color(self, bar_element) -> str | None:
        """Extract background color from a progress bar element."""
        style = bar_element.get("style", "")
        if "background-color:" not in style:
            return None

        # Parse the style attribute
        style_parts = style.split(";")
        for part in style_parts:
            if "background-color:" in part:
                bg_color = part.split(":")[1].strip()
                logger.debug(f"Found background color: {bg_color}")
                return bg_color

        return None

    def _extract_width_percentage(self, bar_element) -> float | None:
        """Extract width percentage from a progress bar element."""
        try:
            # Get the style attribute
            style = bar_element.get("style", "")

            # Parse style for width
            style_parts = style.split(";")
            for part in style_parts:
                if "width:" in part:
                    width_part = part.split(":")[1].strip()
                    if "%" in width_part:
                        width_percent = float(width_part.replace("%", ""))
                        logger.debug(f"Using width percentage: {width_percent:.4f}%")
                        return width_percent

            return None

        except Exception as e:
            logger.error(f"Error extracting width percentage: {e}")
            return None

    def _parse_team_metrics_from_html(self, html: str) -> dict:
        """Parse detailed team metrics from the event page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        metrics = {
            'team1_users': None,
            'team2_users': None,
            'team1_attacks': None,
            'team2_attacks': None,
            'team1_friendly_fire': None,
            'team2_friendly_fire': None,
            'team1_battle_ratio': None,
            'team2_battle_ratio': None,
            'team1_avg_points': None,
            'team2_avg_points': None,
            'team1_avg_attacks': None,
            'team2_avg_attacks': None,
        }

        try:
            # Look for team statistics cards with the specific structure from the HTML
            # Structure: <div class="col-md-6"><div class="card"><div class="card-header">...</div><div class="card-body">...</div></div></div>
            team_cards = soup.find_all("div", class_="col-md-6")
            
            logger.debug(f"Found {len(team_cards)} potential team cards")
            
            for card in team_cards:
                # Look for the card structure
                card_div = card.find("div", class_="card")
                if not card_div:
                    continue
                
                # Find the card header with team name
                card_header = card_div.find("div", class_="card-header")
                if not card_header:
                    continue
                
                # Extract team name from the link in the header
                # Structure: <strong><a href="/team/21.fossils">Fossils</a></strong>
                team_link = card_header.find("a")
                if not team_link:
                    continue
                
                team_name = team_link.get_text(strip=True)
                if not team_name:
                    continue
                
                logger.debug(f"Found team card for: {team_name}")
                
                # Determine which team this is based on configured team names
                if not settings.teams:
                    continue
                    
                is_team1 = settings.teams.team1.name.lower() in team_name.lower()
                is_team2 = settings.teams.team2.name.lower() in team_name.lower()
                
                if not (is_team1 or is_team2):
                    logger.debug(f"Team '{team_name}' not in configured teams, skipping")
                    continue
                
                team_prefix = "team1" if is_team1 else "team2"
                logger.debug(f"Processing metrics for {team_prefix}: {team_name}")
                
                # Find the card body with metrics
                card_body = card_div.find("div", class_="card-body")
                if not card_body:
                    continue
                
                # Parse metrics from the card body
                # Structure: <h4>272912 <small>users</small></h4>
                self._parse_metric_from_card_body(card_body, team_prefix, "users", r'(\d+)', 'users', metrics, int)
                self._parse_metric_from_card_body(card_body, team_prefix, "attacks", r'(\d+)', 'attacks', metrics, int)
                self._parse_metric_from_card_body(card_body, team_prefix, "friendly fire attacks", r'(\d+)', 'friendly_fire', metrics, int)
                self._parse_metric_from_card_body(card_body, team_prefix, "battle ratio", r'([\d.]+)', 'battle_ratio', metrics, float)
                self._parse_metric_from_card_body(card_body, team_prefix, "average points", r'([\d.]+)', 'avg_points', metrics, float)
                self._parse_metric_from_card_body(card_body, team_prefix, "average attacks", r'([\d.]+)', 'avg_attacks', metrics, float)
            
            logger.debug(f"Parsed team metrics: {metrics}")
            
        except Exception as e:
            logger.error(f"Error parsing team metrics: {e}")
        
        return metrics

    def _parse_metric_from_card_body(self, card_body, team_prefix: str, search_text: str, 
                                    regex_pattern: str, metric_name: str, metrics: dict, 
                                    value_type: type) -> None:
        """Parse a specific metric from a card body using the ArtFight HTML structure."""
        try:
            # Look for h4 elements with small tags (ArtFight's specific structure)
            # Structure: <h4>272912 <small>users</small></h4>
            for h4_elem in card_body.find_all('h4'):
                small_elem = h4_elem.find('small')
                if small_elem and search_text.lower() in small_elem.get_text().lower():
                    # Extract the number from the h4 text (before the small tag)
                    h4_text = h4_elem.get_text()
                    # Remove the small tag text to get just the number
                    small_text = small_elem.get_text()
                    number_text = h4_text.replace(small_text, '').strip()
                    match = re.search(regex_pattern, number_text)
                    if match:
                        metric_value = value_type(match.group(1))
                        metrics[f'{team_prefix}_{metric_name}'] = metric_value
                        logger.debug(f"Found {team_prefix}_{metric_name}: {metric_value}")
                        return
            
            logger.debug(f"Could not find {metric_name} for {team_prefix}")
                
        except Exception as e:
            logger.debug(f"Error parsing {metric_name} for {team_prefix}: {e}")

    def _parse_metric_from_section(self, section, team_prefix: str, search_text: str, 
                                  regex_pattern: str, metric_name: str, metrics: dict, 
                                  value_type: type) -> None:
        """Helper method to parse a specific metric from a section."""
        try:
            # Try multiple approaches to find the metric
            metric_value = None
            
            # Approach 1: Look for h4 elements with small tags (ArtFight's specific structure)
            # This matches the structure: <h4>267217 <small>users</small></h4>
            for h4_elem in section.find_all('h4'):
                small_elem = h4_elem.find('small')
                if small_elem and search_text.lower() in small_elem.get_text().lower():
                    # Extract the number from the h4 text (before the small tag)
                    h4_text = h4_elem.get_text()
                    # Remove the small tag text to get just the number
                    small_text = small_elem.get_text()
                    number_text = h4_text.replace(small_text, '').strip()
                    match = re.search(regex_pattern, number_text)
                    if match:
                        metric_value = value_type(match.group(1))
                        break
            
            # Approach 2: Find text containing the metric name (fallback)
            if metric_value is None:
                metric_elem = section.find(text=re.compile(search_text, re.I))
                if metric_elem and hasattr(metric_elem, 'parent') and metric_elem.parent:
                    parent_text = metric_elem.parent.get_text()
                    match = re.search(regex_pattern, parent_text)
                    if match:
                        metric_value = value_type(match.group(1))
            
            # Approach 3: Look for elements with data attributes or specific classes
            if metric_value is None:
                # Try to find elements with metric-related classes or IDs
                for elem in section.find_all(text=True):
                    if search_text.lower() in elem.lower():
                        # Look for numbers in nearby elements
                        parent = elem.parent
                        if parent:
                            # Check parent and siblings for numbers
                            for sibling in [parent] + list(parent.find_next_siblings()):
                                sibling_text = sibling.get_text()
                                match = re.search(regex_pattern, sibling_text)
                                if match:
                                    metric_value = value_type(match.group(1))
                                    break
                        if metric_value is not None:
                            break
            
            # Approach 4: Look for table rows or list items containing the metric
            if metric_value is None:
                for elem in section.find_all(['tr', 'li', 'div']):
                    elem_text = elem.get_text()
                    if search_text.lower() in elem_text.lower():
                        match = re.search(regex_pattern, elem_text)
                        if match:
                            metric_value = value_type(match.group(1))
                            break
            
            # Store the metric if found
            if metric_value is not None:
                metrics[f'{team_prefix}_{metric_name}'] = metric_value
                logger.debug(f"Found {team_prefix}_{metric_name}: {metric_value}")
                
        except Exception as e:
            logger.debug(f"Error parsing {metric_name} for {team_prefix}: {e}")

    def _parse_team1_percentage(self, bar_element) -> float | None:
        """Parse team1 percentage from the first progress bar element."""
        try:
            # Extract the style attribute to get width
            style_attr = bar_element.get("style", "")
            logger.debug(f"Parsing team1 progress bar with style: {style_attr}")

            # Extract width percentage
            width_match = re.search(r"width:([\d.]+)%", style_attr)
            if not width_match:
                logger.warning("No width found in progress bar style")
                return None

            width_percent = float(width_match.group(1))

            # Extract percentage text from the bar content as backup
            percentage_text = bar_element.get_text(strip=True)
            percentage_match = re.search(r"([\d.]+)%", percentage_text)
            if percentage_match:
                percentage = float(percentage_match.group(1))
                # Use the text percentage if it's close to the width percentage
                if abs(percentage - width_percent) < 1.0:
                    return percentage

            # Return width percentage as fallback
            return width_percent

        except Exception as e:
            logger.error(f"Error parsing team1 percentage: {e}")
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        logger.debug("Closing ArtFight client")
        await self.client.aclose()
        logger.debug("ArtFight client closed")
